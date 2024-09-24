-- locust_results.events definition

CREATE TABLE `events` (
  `time` timestamp(6) NULL DEFAULT NULL,
  `text` text COLLATE utf8mb4_unicode_ci NOT NULL,
  KEY `idx_events_time` (`time` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- locust_results.request definition

CREATE TABLE `request` (
  `time` timestamp(6) NULL DEFAULT NULL,
  `run_id` timestamp(6) NULL DEFAULT NULL,
  `exception` text COLLATE utf8mb4_unicode_ci,
  `greenlet_id` int NOT NULL,
  `loadgen` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `request_type` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `response_length` int DEFAULT NULL,
  `response_time` double DEFAULT NULL,
  `success` tinyint NOT NULL,
  `testplan` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `pid` int DEFAULT NULL,
  `context` json DEFAULT NULL,
  `url` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  'trino_queryid' varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  'hostname' varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  KEY `idx_request_time` (`time` DESC),
  KEY `idx_request_run_id` (`run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- locust_results.testrun definition

CREATE TABLE `testrun` (
  `id` timestamp(6) NOT NULL,
  `testplan` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `profile_name` text COLLATE utf8mb4_unicode_ci,
  `num_clients` int NOT NULL,
  `rps` double DEFAULT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `end_time` timestamp(6) NULL DEFAULT NULL,
  `env` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `username` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `gitrepo` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `rps_avg` decimal(10,2) DEFAULT NULL,
  `resp_time_avg` decimal(10,2) DEFAULT NULL,
  `changeset_guid` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fail_ratio` double DEFAULT NULL,
  `requests` int DEFAULT NULL,
  `arguments` text COLLATE utf8mb4_unicode_ci,
  `exit_code` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_testrun_id` (`id` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- locust_results.user_count definition

CREATE TABLE `user_count` (
  `testplan` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_count` int NOT NULL,
  `time` timestamp(6) NULL DEFAULT NULL,
  `run_id` timestamp(6) NULL DEFAULT NULL,
  KEY `idx_user_count_time` (`time` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
