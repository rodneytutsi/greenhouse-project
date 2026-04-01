-- ============================================================
--  Smart Greenhouse IoT System — Database Schema
--  Engine  : MySQL 8.0+
--  Charset : utf8mb4 / utf8mb4_unicode_ci
--  Created : 2026
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;
SET SQL_MODE = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- ============================================================
-- 1. USERS
--    Stores all system users (admins, farmers, viewers)
-- ============================================================
CREATE TABLE IF NOT EXISTS `users` (
  `id`              INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  `name`            VARCHAR(120)      NOT NULL,
  `email`           VARCHAR(255)      NOT NULL,
  `password_hash`   VARCHAR(255)      NOT NULL,
  `role`            ENUM('admin','farmer','viewer') NOT NULL DEFAULT 'farmer',
  `phone`           VARCHAR(20)       NULL DEFAULT NULL COMMENT 'Used for SMS alerts',
  `push_token`      VARCHAR(512)      NULL DEFAULT NULL COMMENT 'Mobile push notification token',
  `is_active`       TINYINT(1)        NOT NULL DEFAULT 1,
  `last_login_at`   TIMESTAMP         NULL DEFAULT NULL,
  `created_at`      TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`      TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_email` (`email`),
  INDEX `idx_users_role` (`role`),
  INDEX `idx_users_is_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='System users — admins, farmers, and read-only viewers';


-- ============================================================
-- 2. GREENHOUSES
--    A user can own/manage multiple greenhouse zones
-- ============================================================
CREATE TABLE IF NOT EXISTS `greenhouses` (
  `id`              INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  `user_id`         INT UNSIGNED      NOT NULL,
  `name`            VARCHAR(150)      NOT NULL,
  `description`     TEXT              NULL DEFAULT NULL,
  `location`        VARCHAR(255)      NULL DEFAULT NULL COMMENT 'Physical address or GPS coords',
  `latitude`        DECIMAL(10, 7)    NULL DEFAULT NULL,
  `longitude`       DECIMAL(10, 7)    NULL DEFAULT NULL,
  `area_sqm`        DECIMAL(10, 2)    NULL DEFAULT NULL COMMENT 'Floor area in square metres',
  `crop_type`       VARCHAR(100)      NULL DEFAULT NULL COMMENT 'E.g. Tomatoes, Lettuce, Herbs',
  `image_url`       VARCHAR(512)      NULL DEFAULT NULL,
  `is_active`       TINYINT(1)        NOT NULL DEFAULT 1,
  `created_at`      TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`      TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (`id`),
  INDEX `idx_greenhouses_user_id` (`user_id`),
  INDEX `idx_greenhouses_is_active` (`is_active`),
  CONSTRAINT `fk_greenhouses_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Individual greenhouse zones owned by a user';


-- ============================================================
-- 3. SENSORS
--    IoT devices attached to a greenhouse
-- ============================================================
CREATE TABLE IF NOT EXISTS `sensors` (
  `id`              INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  `greenhouse_id`   INT UNSIGNED      NOT NULL,
  `name`            VARCHAR(120)      NOT NULL COMMENT 'Human-readable label, e.g. Zone A Temp',
  `type`            ENUM(
                      'temperature',
                      'humidity',
                      'soil_moisture',
                      'co2',
                      'light',
                      'ph',
                      'ec',
                      'water_level',
                      'wind_speed',
                      'rainfall'
                    ) NOT NULL,
  `mqtt_topic`      VARCHAR(255)      NOT NULL COMMENT 'E.g. greenhouse/1/sensor/temp_a',
  `unit`            VARCHAR(20)       NOT NULL COMMENT 'E.g. °C, %, ppm, lux',
  `model`           VARCHAR(100)      NULL DEFAULT NULL COMMENT 'Hardware model, e.g. DHT22',
  `firmware_ver`    VARCHAR(50)       NULL DEFAULT NULL,
  `location_label`  VARCHAR(100)      NULL DEFAULT NULL COMMENT 'E.g. North corner, Row 3',
  `calibration_offset` DECIMAL(8,4)  NOT NULL DEFAULT 0.0000,
  `is_active`       TINYINT(1)        NOT NULL DEFAULT 1,
  `last_seen_at`    TIMESTAMP         NULL DEFAULT NULL,
  `created_at`      TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`      TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sensors_mqtt_topic` (`mqtt_topic`),
  INDEX `idx_sensors_greenhouse_id` (`greenhouse_id`),
  INDEX `idx_sensors_type` (`type`),
  INDEX `idx_sensors_is_active` (`is_active`),
  CONSTRAINT `fk_sensors_greenhouse`
    FOREIGN KEY (`greenhouse_id`) REFERENCES `greenhouses` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='IoT sensors attached to each greenhouse zone';


-- ============================================================
-- 4. SENSOR_READINGS
--    Time-series table — high insert volume, partitioned by month
--    Note: For very high-frequency data (>1 reading/sec per sensor),
--          consider mirroring this to InfluxDB via the PHP MQTT bridge.
-- ============================================================
CREATE TABLE IF NOT EXISTS `sensor_readings` (
  `id`              BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
  `sensor_id`       INT UNSIGNED      NOT NULL,
  `value`           DECIMAL(12, 4)    NOT NULL,
  `raw_payload`     JSON              NULL DEFAULT NULL COMMENT 'Full MQTT payload if needed',
  `quality`         TINYINT UNSIGNED  NOT NULL DEFAULT 100 COMMENT '0-100 signal quality score',
  `recorded_at`     TIMESTAMP(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

  PRIMARY KEY (`id`, `recorded_at`),
  INDEX `idx_readings_sensor_recorded` (`sensor_id`, `recorded_at` DESC),
  INDEX `idx_readings_recorded_at` (`recorded_at` DESC),
  CONSTRAINT `fk_readings_sensor`
    FOREIGN KEY (`sensor_id`) REFERENCES `sensors` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Raw time-series sensor readings streamed from MQTT'
  PARTITION BY RANGE (UNIX_TIMESTAMP(`recorded_at`)) (
    PARTITION p_2026_q1 VALUES LESS THAN (UNIX_TIMESTAMP('2026-04-01')),
    PARTITION p_2026_q2 VALUES LESS THAN (UNIX_TIMESTAMP('2026-07-01')),
    PARTITION p_2026_q3 VALUES LESS THAN (UNIX_TIMESTAMP('2026-10-01')),
    PARTITION p_2026_q4 VALUES LESS THAN (UNIX_TIMESTAMP('2027-01-01')),
    PARTITION p_future   VALUES LESS THAN MAXVALUE
  );


-- ============================================================
-- 5. ALERT_RULES
--    Threshold rules that define when an alert should fire
-- ============================================================
CREATE TABLE IF NOT EXISTS `alert_rules` (
  `id`              INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  `sensor_id`       INT UNSIGNED      NOT NULL,
  `name`            VARCHAR(150)      NOT NULL COMMENT 'E.g. High temp warning',
  `condition`       ENUM('above','below','outside_range','inside_range') NOT NULL,
  `threshold_min`   DECIMAL(12, 4)    NULL DEFAULT NULL,
  `threshold_max`   DECIMAL(12, 4)    NULL DEFAULT NULL,
  `duration_seconds` SMALLINT UNSIGNED NOT NULL DEFAULT 0
                    COMMENT 'How long condition must persist before alerting',
  `severity`        ENUM('info','warning','critical') NOT NULL DEFAULT 'warning',
  `notify_via`      SET('email','sms','push','dashboard') NOT NULL DEFAULT 'email,dashboard',
  `cooldown_minutes` SMALLINT UNSIGNED NOT NULL DEFAULT 30
                    COMMENT 'Minimum minutes between repeated alerts for same rule',
  `is_active`       TINYINT(1)        NOT NULL DEFAULT 1,
  `created_at`      TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`      TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (`id`),
  INDEX `idx_alert_rules_sensor_id` (`sensor_id`),
  INDEX `idx_alert_rules_is_active` (`is_active`),
  CONSTRAINT `fk_alert_rules_sensor`
    FOREIGN KEY (`sensor_id`) REFERENCES `sensors` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Configurable threshold rules that govern when alerts are raised';


-- ============================================================
-- 6. ALERTS
--    Alert events raised when a rule condition is breached
-- ============================================================
CREATE TABLE IF NOT EXISTS `alerts` (
  `id`              INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  `greenhouse_id`   INT UNSIGNED      NOT NULL,
  `sensor_id`       INT UNSIGNED      NOT NULL,
  `alert_rule_id`   INT UNSIGNED      NULL DEFAULT NULL,
  `severity`        ENUM('info','warning','critical') NOT NULL DEFAULT 'warning',
  `message`         TEXT              NOT NULL,
  `trigger_value`   DECIMAL(12, 4)    NULL DEFAULT NULL COMMENT 'The reading that fired this alert',
  `is_resolved`     TINYINT(1)        NOT NULL DEFAULT 0,
  `resolved_by`     INT UNSIGNED      NULL DEFAULT NULL COMMENT 'User who marked resolved',
  `resolution_note` TEXT              NULL DEFAULT NULL,
  `triggered_at`    TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `resolved_at`     TIMESTAMP         NULL DEFAULT NULL,

  PRIMARY KEY (`id`),
  INDEX `idx_alerts_greenhouse_id` (`greenhouse_id`),
  INDEX `idx_alerts_sensor_id` (`sensor_id`),
  INDEX `idx_alerts_is_resolved` (`is_resolved`),
  INDEX `idx_alerts_severity` (`severity`),
  INDEX `idx_alerts_triggered_at` (`triggered_at` DESC),
  CONSTRAINT `fk_alerts_greenhouse`
    FOREIGN KEY (`greenhouse_id`) REFERENCES `greenhouses` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_alerts_sensor`
    FOREIGN KEY (`sensor_id`) REFERENCES `sensors` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_alerts_rule`
    FOREIGN KEY (`alert_rule_id`) REFERENCES `alert_rules` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_alerts_resolved_by`
    FOREIGN KEY (`resolved_by`) REFERENCES `users` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Alert events raised when sensor thresholds are breached';


-- ============================================================
-- 7. NOTIFICATION_LOG
--    Full delivery audit trail for every alert notification
-- ============================================================
CREATE TABLE IF NOT EXISTS `notification_log` (
  `id`              BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
  `alert_id`        INT UNSIGNED      NOT NULL,
  `user_id`         INT UNSIGNED      NOT NULL,
  `channel`         ENUM('email','sms','push','dashboard') NOT NULL,
  `recipient`       VARCHAR(255)      NOT NULL COMMENT 'Email addr, phone number, or device token',
  `subject`         VARCHAR(255)      NULL DEFAULT NULL,
  `message`         TEXT              NOT NULL,
  `delivered`       TINYINT(1)        NOT NULL DEFAULT 0,
  `provider_ref`    VARCHAR(255)      NULL DEFAULT NULL COMMENT 'E.g. SendGrid message ID, Twilio SID',
  `error_message`   TEXT              NULL DEFAULT NULL,
  `retry_count`     TINYINT UNSIGNED  NOT NULL DEFAULT 0,
  `sent_at`         TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `delivered_at`    TIMESTAMP         NULL DEFAULT NULL,

  PRIMARY KEY (`id`),
  INDEX `idx_notif_alert_id` (`alert_id`),
  INDEX `idx_notif_user_id` (`user_id`),
  INDEX `idx_notif_channel` (`channel`),
  INDEX `idx_notif_delivered` (`delivered`),
  CONSTRAINT `fk_notif_alert`
    FOREIGN KEY (`alert_id`) REFERENCES `alerts` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_notif_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Delivery audit log for all alert notifications across channels';


-- ============================================================
-- 8. AI_PREDICTIONS
--    Crop health analysis output from the Python ML model
-- ============================================================
CREATE TABLE IF NOT EXISTS `ai_predictions` (
  `id`              INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  `greenhouse_id`   INT UNSIGNED      NOT NULL,
  `model_version`   VARCHAR(50)       NOT NULL DEFAULT 'v1.0' COMMENT 'ML model version used',
  `crop_status`     ENUM(
                      'healthy',
                      'needs_attention',
                      'stressed',
                      'diseased',
                      'critical'
                    ) NOT NULL,
  `confidence`      DECIMAL(5, 4)     NOT NULL COMMENT '0.0000 to 1.0000',
  `recommendation`  TEXT              NOT NULL,
  `risk_factors`    JSON              NULL DEFAULT NULL COMMENT 'Array of detected risk factors',
  `raw_features`    JSON              NOT NULL COMMENT 'Sensor snapshot used for prediction',
  `predicted_at`    TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (`id`),
  INDEX `idx_ai_greenhouse_id` (`greenhouse_id`),
  INDEX `idx_ai_crop_status` (`crop_status`),
  INDEX `idx_ai_predicted_at` (`predicted_at` DESC),
  INDEX `idx_ai_confidence` (`confidence`),
  CONSTRAINT `fk_ai_greenhouse`
    FOREIGN KEY (`greenhouse_id`) REFERENCES `greenhouses` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='AI/ML crop health predictions generated per greenhouse';


-- ============================================================
-- 9. ACTUATORS
--    Controllable devices (pumps, fans, vents, lights)
--    Ready for future automation module
-- ============================================================
CREATE TABLE IF NOT EXISTS `actuators` (
  `id`              INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  `greenhouse_id`   INT UNSIGNED      NOT NULL,
  `name`            VARCHAR(120)      NOT NULL COMMENT 'E.g. Irrigation Pump Zone A',
  `type`            ENUM(
                      'irrigation_pump',
                      'ventilation_fan',
                      'grow_light',
                      'heater',
                      'vent_window',
                      'co2_injector',
                      'nutrient_pump',
                      'shade_screen'
                    ) NOT NULL,
  `mqtt_command_topic` VARCHAR(255)   NOT NULL COMMENT 'Topic to publish ON/OFF commands',
  `mqtt_status_topic`  VARCHAR(255)   NULL DEFAULT NULL COMMENT 'Topic that reports current state',
  `current_state`   ENUM('on','off','unknown') NOT NULL DEFAULT 'unknown',
  `is_auto`         TINYINT(1)        NOT NULL DEFAULT 0 COMMENT 'Under automation control',
  `is_active`       TINYINT(1)        NOT NULL DEFAULT 1,
  `last_commanded_at` TIMESTAMP       NULL DEFAULT NULL,
  `created_at`      TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`      TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_actuator_command_topic` (`mqtt_command_topic`),
  INDEX `idx_actuators_greenhouse_id` (`greenhouse_id`),
  INDEX `idx_actuators_type` (`type`),
  CONSTRAINT `fk_actuators_greenhouse`
    FOREIGN KEY (`greenhouse_id`) REFERENCES `greenhouses` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Controllable IoT actuators (pumps, fans, lights, etc.)';


-- ============================================================
-- 10. ACTUATOR_LOG
--     Every command issued to an actuator
-- ============================================================
CREATE TABLE IF NOT EXISTS `actuator_log` (
  `id`              BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
  `actuator_id`     INT UNSIGNED      NOT NULL,
  `commanded_by`    INT UNSIGNED      NULL DEFAULT NULL COMMENT 'NULL = automated rule',
  `action`          ENUM('on','off','toggle') NOT NULL,
  `trigger_source`  ENUM('manual','automation','alert','schedule','api') NOT NULL DEFAULT 'manual',
  `note`            VARCHAR(255)      NULL DEFAULT NULL,
  `commanded_at`    TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (`id`),
  INDEX `idx_act_log_actuator_id` (`actuator_id`),
  INDEX `idx_act_log_commanded_at` (`commanded_at` DESC),
  CONSTRAINT `fk_act_log_actuator`
    FOREIGN KEY (`actuator_id`) REFERENCES `actuators` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_act_log_user`
    FOREIGN KEY (`commanded_by`) REFERENCES `users` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Command history for all actuator actions';


-- ============================================================
-- SEED DATA — Default admin user (change password immediately)
-- Password: greenhouse2026!  (bcrypt hash)
-- ============================================================
INSERT INTO `users` (`name`, `email`, `password_hash`, `role`) VALUES
(
  'System Admin',
  'admin@greenhouse.local',
  '$2y$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2uheWG/igi.',
  'admin'
);

-- ============================================================
-- Demo greenhouse linked to admin user (id = 1)
-- ============================================================
INSERT INTO `greenhouses` (`user_id`, `name`, `description`, `location`, `area_sqm`, `crop_type`) VALUES
(1, 'Greenhouse Alpha', 'Primary research greenhouse — Zone A', 'Block 1, North Farm', 250.00, 'Tomatoes');

-- ============================================================
-- Demo sensors for Greenhouse Alpha (id = 1)
-- ============================================================
INSERT INTO `sensors` (`greenhouse_id`, `name`, `type`, `mqtt_topic`, `unit`, `model`, `location_label`) VALUES
(1, 'Air Temperature', 'temperature',  'gh/1/sensor/air_temp',    '°C',  'DHT22',    'Center canopy'),
(1, 'Air Humidity',    'humidity',     'gh/1/sensor/air_hum',     '%',   'DHT22',    'Center canopy'),
(1, 'Soil Moisture A', 'soil_moisture','gh/1/sensor/soil_moist_a','%',   'VH400',    'Row 1 bed'),
(1, 'CO2 Level',       'co2',          'gh/1/sensor/co2',         'ppm', 'MH-Z19B',  'East wall'),
(1, 'Light (PAR)',     'light',        'gh/1/sensor/light',       'lux', 'BH1750',   'Roof center');

-- ============================================================
-- Demo alert rules for temperature and soil moisture
-- ============================================================
INSERT INTO `alert_rules` (`sensor_id`, `name`, `condition`, `threshold_min`, `threshold_max`, `severity`, `notify_via`, `cooldown_minutes`) VALUES
(1, 'High temperature warning', 'above', NULL,  35.00, 'warning',  'email,dashboard',     30),
(1, 'Frost risk alert',         'below', 5.00,  NULL,  'critical', 'email,sms,dashboard', 15),
(3, 'Low soil moisture',        'below', 25.00, NULL,  'warning',  'email,dashboard',     60),
(4, 'CO2 too high',             'above', NULL,  1500.00,'warning', 'dashboard',           45);

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- END OF SCHEMA
-- To import: mysql -u root -p greenhouse_db < greenhouse_schema.sql
-- ============================================================
