# Smart_EV_Charging_Station_Management_System_SQL
-------------------------------------------------

Smart EV Charging Station Management System is a SQL-based database project for managing EV charging services.
It allows users to register vehicles, book charging slots, track charging sessions, make payments, and view charging history, 
while enabling administrators to manage stations, chargers, tariffs, memberships, and reports.

Total Tables: 17
No	Table	Purpose
1	Roles	Customer, Operator, Admin
2	Users	Stores all users
3	MembershipPlans	Subscription plans
4	UserMemberships	User subscriptions
5	EVVehicles	User vehicles
6	ChargingStations	Charging station details
7	Chargers	Chargers inside stations
8	Tariffs	Charging prices
9	Bookings	Slot bookings
10	ChargingSessions	Charging session details
11	Payments	Payment records
12	WalletTransactions	Wallet recharge/payment history
13	Reviews	Station reviews
14	Maintenance	Charger maintenance
15	Notifications	User notifications
16	LoginHistory	Login audit
17	AuditLogs	System audit logs


Roles (1)
   │
   │
Users (M)
   │
   ├──────────── EVVehicles
   │
   ├──────────── UserMemberships ───── MembershipPlans
   │
   ├──────────── Bookings
   │                 │
   │                 ▼
   │          ChargingSessions
   │                 │
   │                 ▼
   │             Payments
   │
   ├──────────── WalletTransactions
   │
   ├──────────── Reviews
   │
   ├──────────── Notifications
   │
   ├──────────── LoginHistory
   │
   └──────────── AuditLogs

ChargingStations
        │
        │
        ▼
    Chargers
        │
        ▼
     Tariffs
        │
        ▼
Bookings
