# EV Data Quality Monitor - ETL

The ETL performs a full load from `Smart_EV_Charging_System` into the separate
`ev_reporting` database.

## Target tables

- `fact_charging_sessions`: session-level reporting fact joined to customer,
  vehicle, charger, station, tariff, and payment dimensions.
- `daily_station_revenue`: successful payment revenue and delivered energy by
  station and date.
- `daily_slot_utilization`: booked minutes and utilization for each charger/day.

## Setup

1. Load `EV_Management_Project.sql` and `EV_Management_Records.sql` into MySQL.
2. Create the target database and tables:

   ```sql
   SOURCE sql/target_schema.sql
   ```

3. Install the Python dependency:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Set database connection variables in PowerShell:

   ```powershell
   Copy-Item .env.example .env
   $env:SOURCE_HOST="127.0.0.1"
   $env:SOURCE_USER="root"
   $env:SOURCE_PASSWORD="your_password"
   $env:TARGET_HOST="127.0.0.1"
   $env:TARGET_USER="root"
   $env:TARGET_PASSWORD="your_password"
   ```

5. Run the full load:

   ```powershell
   python etl_load.py
   ```

The load is transactional. It replaces the target fact and aggregate tables only
when the complete extraction and target writes succeed.
