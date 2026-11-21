CREATE DATABASE IF NOT EXISTS ev_reporting;
USE ev_reporting;

DROP TABLE IF EXISTS daily_slot_utilization;
DROP TABLE IF EXISTS daily_station_revenue;
DROP TABLE IF EXISTS fact_charging_sessions;

CREATE TABLE fact_charging_sessions (
    SessionID INT PRIMARY KEY,
    BookingID INT,
    UserID INT,
    CustomerName VARCHAR(100),
    VehicleID INT,
    VehicleMake VARCHAR(50),
    VehicleModel VARCHAR(50),
    ChargerID INT,
    ChargerCode VARCHAR(30),
    StationID INT,
    StationName VARCHAR(100),
    SessionStartTime DATETIME,
    SessionEndTime DATETIME,
    SessionDurationMinutes INT,
    EstimatedCompletionTime DATETIME,
    EnergyDeliveredKWh DECIMAL(8,3),
    SessionStatus VARCHAR(20),
    PaymentID INT,
    PaymentAmount DECIMAL(10,2),
    PaymentStatus VARCHAR(20),
    TransactionDate DATETIME,
    TariffID INT,
    PricePerKWh DECIMAL(6,2),
    LoadedAt DATETIME NOT NULL
);

CREATE TABLE daily_station_revenue (
    StationID INT,
    StationName VARCHAR(100),
    RevenueDate DATE,
    SuccessfulPaymentCount INT,
    RevenueAmount DECIMAL(12,2),
    EnergyDeliveredKWh DECIMAL(12,3),
    PRIMARY KEY (StationID, RevenueDate)
);

CREATE TABLE daily_slot_utilization (
    ChargerID INT,
    ChargerCode VARCHAR(30),
    StationID INT,
    UtilizationDate DATE,
    ActiveBookingCount INT,
    BookedMinutes INT,
    AvailableMinutes INT,
    UtilizationPercent DECIMAL(7,2),
    PRIMARY KEY (ChargerID, UtilizationDate)
);
