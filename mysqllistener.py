from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import json
import logging
from typing import List
import gevent
from gevent.lock import Semaphore
import greenlet
import locust
import locust.env
import os, socket
import atexit
import mysql.connector
from zmq import NULL
import sys
from mysql.connector import Error
from mysql.connector.cursor import MySQLCursorDict

from locust import events
from locust.argument_parser import LocustArgumentParser

def add_mysql_arguments(parser: LocustArgumentParser):
    # Add custom MySQL arguments
    parser.add_argument("--msqlhost", type=str, env_var="MYSQL_HOST",  help="MySQL host")
    parser.add_argument("--msqluser", type=str, env_var="MYSQL_USER", help="MySQL user")
    parser.add_argument("--msqlpassword", type=str, env_var="MYSQL_PASSWORD", help="MySQL password")
    parser.add_argument("--msqldatabase", type=str, env_var="MYSQL_DATABASE",  help="MySQL database")
    parser.add_argument("--msqlport", type=int, env_var="MYSQL_PORT",  help="MySQL port")
    parser.add_argument("--testplan", type=str, env_var="testplan",  help="Test Plan Name")

# Hook into the event to add custom MySQL arguments to the parser
@events.init_command_line_parser.add_listener
def on_init_command_line_parser(parser: LocustArgumentParser):
    add_mysql_arguments(parser)

def safe_serialize(obj):
    def default(o):
        return f"<<non-serializable: {type(o).__qualname__}>>"
    return json.dumps(obj, default=default)

class MySQLDatabase:
    dblock = Semaphore()
    first_instance = True

    @contextmanager
    def dbcursor(self):
        with self.dblock:
            try:
                if not self.dbconn.is_connected():
                    self.dbconn = self._dbconn()
                yield self.dbconn.cursor(buffered=True)
            except mysql.connector.Error:
                try:
                    # try to recreate connection
                    self.dbconn = self._dbconn()
                except:
                    pass
                raise

    def _dbconn(self):
        if self.env.parsed_options is None:
            raise ValueError("parsed_options is not initialized")
        try:
            conn = mysql.connector.connect(
                host=self.env.parsed_options.msqlhost,
                user=self.env.parsed_options.msqluser,
                password=self.env.parsed_options.msqlpassword,
                database=self.env.parsed_options.msqldatabase,
                port=self.env.parsed_options.msqlport,
            )
        except mysql.connector.Error as e:
            logging.error(f"Could not connect to MySQL: {e}")
            raise
        return conn

    def __init__(self, env: locust.env.Environment,testplan: str,target_env: str = os.getenv("LOCUST_TEST_ENV", "")):
        if not MySQLDatabase.first_instance:
            # we should refactor this into a module as it is much more pythonic
            raise Exception(
                "You tried to initialize the MySQLDatabase listener twice, maybe both in your locustfile and using command line --mysql? Ignoring second initialization."
            )
        MySQLDatabase.first_instance = False
        self.env = env
        self._samples: List[dict] = []
        self._background = gevent.spawn(self._run)
        self._hostname = socket.gethostname()  # pylint: disable=no-member
        self._username = os.getenv("USER", "unknown")
        self._finished = False
        self._pid = os.getpid()
        events = self.env.events
        events.quit.add_listener(self.on_quit)
        events.test_start.add_listener(self.on_test_start)
        #events.test_stop.add_listener(self.on_test_stop)
        events.request.add_listener(self.on_request)
        events.spawning_complete.add_listener(self.spawning_complete)
        events.quit.add_listener(self.on_quit)
        if self.env.runner is not None:
            self.env.runner.register_message("run_id", self.set_run_id)

    def set_run_id(self, environment, msg, **kwargs):
        logging.debug(f"run id from master: {msg.data}")
        environment._run_id = datetime.strptime(msg.data, "%Y-%m-%d, %H:%M:%S.%f").replace(tzinfo=timezone.utc)
        

    def _run(self):
        while True:
            if self._samples:
                # Buffer samples, so that a locust greenlet will write to the new list
                # instead of the one that has been sent into postgres client
                samples_buffer = self._samples
                self._samples = []
                self.write_samples_to_db(samples_buffer)
            else:
                if self._finished:
                    break
            gevent.sleep(0.5)

    def write_samples_to_db(self, samples):
        try:
            with self.dbcursor() as cur:
                cur.executemany(
                    """INSERT INTO request(time,run_id,greenlet_id,loadgen,name,request_type,response_time,success,testplan,response_length,exception,pid,url,context) 
                    VALUES (%(time)s, %(run_id)s, %(greenlet_id)s, %(loadgen)s, %(name)s, %(request_type)s, %(response_time)s, %(success)s, %(testplan)s, %(response_length)s, %(exception)s, %(pid)s, %(url)s, %(context)s)""",
                    samples
                )
                self.dbconn.commit()
            #print("Query : ",cur._executed)
        except mysql.connector.Error as error:
            logging.error("Failed to write samples to MySQL: " + repr(error))
            sys.exit(1)

    def on_quit(self, exit_code, **kwargs):
        self._finished = True
        atexit._clear()  # make sure we dont capture additional ctrl-c:s # pylint: disable=protected-access
        self._background.join(timeout=10)
        if getattr(self, "_user_count_logger", False):
            self._user_count_logger.kill()
        self.log_stop_test_run(exit_code)

    def log_stop_test_run(self, exit_code=None):
        if self.env.parsed_options is None:
            raise ValueError("parsed_options is not initialized")
        print(f"Test run id {self._run_id} stopping")
        if self.env.parsed_options.worker:
            return  # only run on master or standalone
        if getattr(self, "dbconn", None) is None:
            return  # test_start never ran, so there's not much for us to do
        end_time = datetime.now(timezone.utc)
        #self.write_samples_to_db(self._samples)
        try:
            with self.dbcursor() as cur:
                # Update the end time and exit code for the test run
                try:
                    cur.execute(
                        "UPDATE testrun SET end_time = %s, exit_code = %s WHERE id = %s",
                        (end_time, exit_code, self._run_id),
                    )
                    self.dbconn.commit()
                    print("Query : ",cur._executed)
                except mysql.connector.Error as error:
                    logging.error(
                        "insert into log_stop_test_run: " + repr(error)
                    )
                
                # Log an event for the test run completion
                try:
                    cur.execute(
                        "INSERT INTO events (time, text) VALUES (%s, %s)",
                        (end_time, self._testplan + f" finished with exit code: {exit_code}"),
                    )
                    self.dbconn.commit()
                    print("Query : ",cur._executed)
                except mysql.connector.Error as error:
                    logging.error(
                        "insert into log_stop_test_run: " + repr(error)
                    )

                # Calculate test statistics: total requests, average response time, requests per second, and failure ratio
                try:
                    cur.execute(
                        """
                        SELECT 
                            COUNT(*) AS reqs,
                            AVG(response_time) AS resp_time_avg,
                            TIMESTAMPDIFF(SECOND, MIN(time), MAX(time)) AS duration,
                            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS fails
                        FROM request 
                        WHERE run_id = %s AND time > %s
                        """,
                        (self._run_id, self._run_id)  # Assuming _run_id represents the start time
                    )

                    result = cur.fetchone()
                    if result is not None:
                        reqs = result[0] if result[0] is not None else 0
                        resp_time_avg = result[1] if result[1] is not None else 0
                        duration = result[2] if result[2] is not None else 1  # Prevent division by zero
                        fails = result[3] if result[3] is not None else 0

                        # Calculate requests per second and failure ratio
                        rps_avg = reqs / max(duration, 1)
                        fail_ratio = fails / reqs if reqs > 0 else 0

                        # Now, update the testrun table with the calculated statistics
                        cur.execute(
                            """
                            UPDATE testrun 
                            SET requests = %s, resp_time_avg = %s, rps_avg = %s, fail_ratio = %s 
                            WHERE id = %s
                            """,
                            (reqs, resp_time_avg, rps_avg, fail_ratio, self._run_id)
                        )
                    else:
                        logging.info("No requests logged for this test run.")
                    self.dbconn.commit()
                except mysql.connector.Error as e:
                    logging.info(
                        e.msg
                    )
        except mysql.connector.Error as error:
            logging.error(
                "Failed to update testrun record (or events) with end time to MySQL database: " + repr(error)
            )

        # Log report URL for Grafana (if applicable)
        logging.info(
            f"Report: {self.env.parsed_options.grafana_url}&var-testplan={self._testplan}&from={int(self._run_id.timestamp() * 1000)}&to={int((end_time.timestamp() + 1) * 1000)}\n"
        )
    
    def on_test_start(self, environment: locust.env.Environment, **kwargs):
        if self.env.parsed_options is None:
            raise ValueError("parsed_options is not initialized")
        self._testplan = self.env.parsed_options.testplan or self.env.parsed_options.locustfile
        try:
            self.dbconn = self._dbconn()
            print("db connection successful")
        except mysql.connector.Error as e:
            logging.error(e)
            sys.exit(1)
        if not self.env.parsed_options.worker:
            self._run_id = datetime.now(timezone.utc)
            msg = self._run_id.strftime("%Y-%m-%d, %H:%M:%S.%f")
            if environment.runner is not None:
                print(f"about to send run_id to workers: {msg}")
                environment.runner.send_message("run_id", msg)
            self.log_start_testrun()
            self._user_count_logger = gevent.spawn(self._log_user_count)
        print("Test start")

    def spawning_complete(self, user_count):
        if self.env.parsed_options is None:
            raise ValueError("parsed_options is not initialized")
        if not self.env.parsed_options.worker:  # only log for master/standalone
            end_time = datetime.now(timezone.utc)
            try:
                with self.dbcursor() as cur:
                    try:
                        cur.execute(
                            "INSERT INTO events (time, text) VALUES (%s, %s)",
                            (end_time, f"{self._testplan} rampup complete, {user_count} users spawned"),
                        )
                        self.dbconn.commit()
                        print("Query : ",cur._executed)
                    except mysql.connector.Error as error:
                        logging.error(
                            "insert into spawning_complete: " + repr(error)
                        )
            except mysql.connector.Error as error:
                logging.error(
                    "Failed to insert rampup complete event time to MySQL database: " + repr(error)
                )

    def log_start_testrun(self):
        if self.env.parsed_options is None:
            raise ValueError("parsed_options is not initialized")
        cmd = sys.argv[1:]
        #print("INSERT INTO testrun (id, testplan, num_clients, rps, description, env, profile_name, username, gitrepo, changeset_guid, arguments) VALUES ('",self._run_id,"',")
        with self.dbcursor() as cur:
            try:
                
                cur.execute(
                    "INSERT INTO testrun (id, testplan, num_clients, rps, description, env, profile_name, username, gitrepo, changeset_guid, arguments) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        self._run_id,
                        self._testplan,
                        self.env.parsed_options.num_users or 1,
                        self.env.parsed_options.ips,
                        self.env.parsed_options.description,
                        self.env.parsed_options.test_env,
                        self.env.parsed_options.profile,
                        self._username,
                        "",#self._gitrepo,
                        self.env.parsed_options.test_version,
                        " ".join(cmd),
                    ),
                )
                print("Query : ",cur._executed)
            except mysql.connector.Error as error:
                logging.error(
                    "insert into test run: " + repr(error)
                )
            cur.execute(
                "INSERT INTO events (time, text) VALUES (%s, %s)",
                (datetime.now(timezone.utc).isoformat(), self._testplan + " started by " + self._username),
            )
            self.dbconn.commit()
            print("Query : ",cur._executed)

    def _log_user_count(self):
        while True:
            if self.env.runner is None:
                return
            try:
                with self.dbcursor() as cur:
                    cur.execute(
                        """INSERT INTO user_count(time, run_id, testplan, user_count) VALUES (%s, %s, %s, %s)""",
                        (datetime.now(timezone.utc), self._run_id, self._testplan, self.env.runner.user_count),
                    )
                    self.dbconn.commit()
            except mysql.connector.Error as error:
                logging.error("Failed to write user count to MySQL: " + repr(error))
                try:
                    self.dbconn = self._dbconn()
                except:
                    pass
            gevent.sleep(2.0)

    def on_request(
        self,
        request_type,
        name,
        response_time,
        response_length,
        exception,
        context,
        start_time=None,
        url=None,
        **kwargs,
    ):
        success = 0 if exception else 1
        if start_time:
            time = datetime.fromtimestamp(start_time, tz=timezone.utc)
        else:
            # some users may not send start_time, so we just make an educated guess
            # (which will be horribly wrong if users spend a lot of time in a with/catch_response-block)
            time = datetime.now(timezone.utc) - timedelta(milliseconds=response_time or 0)
        
        greenlet_id = getattr(greenlet.getcurrent(), "minimal_ident", 0)  # if we're debugging there is no greenlet
        
        # Serialize the context using json.dumps
        serialized_context = json.dumps(context, default=safe_serialize)
        sample = {
            "time": time,
            "run_id": self._run_id,
            "greenlet_id": greenlet_id,
            "loadgen": self._hostname,
            "name": name,
            "request_type": request_type,
            "response_time": response_time,
            "success": success,
            "url": url[0:255] if url else None,
            "testplan": self._testplan,
            "pid": self._pid,
            "context": serialized_context,  # Use JSON serialized context for MySQL
        }
        
        if response_length >= 0:
            sample["response_length"] = response_length
        else:
            sample["response_length"] = None

        if exception:
            try:
                sample["exception"] = repr(exception)
            except AttributeError:
                sample["exception"] = f"{exception.__class__} (and it has no string representation)"
        else:
            sample["exception"] = None

        self._samples.append(sample)

    