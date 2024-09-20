from locust import HttpUser, task, events, between
import time
from mysqllistener import MySQLDatabase


class MyHttpUser(HttpUser):
    @task
    def index(self):
        self.client.post("/authentication/1.0/getResults", {"username": "something"})
        time.sleep(1)
        print("Task executed")

    @task
    def index1(self):
        self.client.post("/authentication/1.0/getResults1", {"username": "something"})
        time.sleep(1)
        print("Task executed")

@events.init.add_listener
def on_locust_init(environment, **_kwargs):
    MySQLDatabase(env=environment, testplan="timescale_listener_ex", target_env="myTestEnv")