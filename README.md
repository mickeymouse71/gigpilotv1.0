# GigPilot

**AI co-pilot for Uber, Lyft, DoorDash and UberEats drivers in San Diego**

Built in 20 days as a single-file progressive web app. No app store. No backend. No subscription. Opens in Chrome on any Android phone.

**Live:** [mickeymouse71.github.io/gigpilotv1.0](https://mickeymouse71.github.io/gigpilotv1.0/)
**Demo:** [mickeymouse71.github.io/gigpilotv1.0/?demo=true](https://mickeymouse71.github.io/gigpilotv1.0/?demo=true)

---

## The problem it solves

Gig drivers make dozens of micro-decisions every shift — where to position, when to switch platforms, whether to chase a surge. Most of these decisions are made on gut feel. GigPilot replaces gut feel with data from three sources: the driver's own trip history, live flight arrivals at SAN airport, and the San Diego event calendar.

---

## Features

### Dashboard
- Live earnings vs daily target ($250 default)
- Trips today, miles tracked, time on shift
- **Action Now card** — a single prescriptive instruction: where to go, which platform, why. Updated every 3 seconds from live data.

### Intelligence Brief
Real-time co-pilot brief for your current location:
- Live SAN airport arrivals (OpenSky Network API) — flights in next 30 min, passenger count, which terminal
- San Diego venue events today — Petco Park, Snapdragon Stadium, Del Mar, Pechanga, La Jolla Playhouse, SDCC
- UCSD campus events (live from calendar.ucsd.edu API) — concerts, sports, festivals
- Your personal hotspot zones — learned from your own trip GPS data
- Holiday platform strategy — when to switch to delivery vs rideshare
- Time-of-day zone recommendations

### Today's Plan
Full-shift roadmap from current time to end of day:
- Weekday and weekend plans are different (UCSD/UTC correctly removed on weekends)
- Airport block uses live flight data, not generic text
- Event blocks auto-insert when major events are scheduled
- Your top zones for this day of week (from trip history) shown at top
- Holiday override when applicable

### Trip Capture
- One-tap trip logging after each ride/delivery
- GPS mileage tracking (starts when you tap Mileage Tracker)
- Pickup coordinates captured at trip start (for accurate hotspot analysis)
- Base fare + tip entered separately — total calculated automatically
- Platform selection: Uber, Lyft, DoorDash, UberEats

### Insights
- Earnings vs $250 target
- Tip conversion rate
- Dead miles analysis — paid vs unpaid miles, IRS deduction calculation
- **Pace card** — compares today's earnings to same weekday in previous weeks. One line: "Trending $218 — push $32 more" or "On track for $263"
- Earnings prediction by end time (8 PM / 10 PM / midnight)

### Settings
- Daily earnings target
- Claude API key (optional — enables AI-powered plan generation)
- Export trips as JSON backup
- Data Inspector — view raw localStorage data for debugging

---

## Intelligence stack

| Signal | Source | Refresh |
|--------|--------|---------|
| SAN airport arrivals | OpenSky Network (free, no auth) | 10 min cache |
| SD venue events | Hardcoded 242 events across 6 venues | Seasonal update |
| UCSD campus events | calendar.ucsd.edu Localist API | 6 hr cache |
| Weather | Open-Meteo API | Per session |
| Driver trip history | localStorage (device only) | Real-time |
| GPS hotspots | Computed from trip pickup coordinates | Per trip |

### Hotspot detection
Trips are clustered by GPS pickup coordinates. Any 5+ trips starting within 0.25 miles of each other form a hotspot. Each hotspot stores: zone name, trip count, average $/mi, average tip, time-of-day distribution. The Intelligence brief surfaces the nearest hotspot when you're within 3 miles.

### Pace engine
Compares cumulative earnings at the current hour against the same cumulative figure from previous same-weekday sessions. A driver who has earned $47 by 9 AM on a Wednesday is compared to what they'd typically earned by 9 AM on past Wednesdays — not against a flat $25/hour target. Projection scales the historical full-day average by the current pace ratio.

### Action prescription hierarchy
1. Airport — live flights arriving in <30 min → GO NOW
2. Major event ending in <45 min → POSITION
3. Behind pace and >$50 remaining → CHANGE STRATEGY
4. 25+ min idle → REPOSITION
5. Default → time-of-day zone from your trip data

---

## Architecture

Single HTML file (~720KB). No build step, no framework, no dependencies.

```
index.html
├── CSS          ~800 lines   Design system, dark theme, component styles
├── HTML         ~1,200 lines Static page structure, 5 tabs, 6 modals
└── JavaScript   ~8,500 lines
    ├── Data layer              localStorage schema, CRUD, migration
    ├── GPS engine              Haversine, zone detection, watchPosition
    ├── Trip capture            v2 schema, pickup/dropoff coords
    ├── Intelligence engine     Airport API, UCSD API, hotspot clustering
    ├── Plan engine             Rule-based + Claude API fallback
    ├── Pace engine             Week-over-week comparison, projection
    ├── Prescription engine     5-priority action recommendation
    ├── Pattern engine          buildPatternContext, buildPersonalSummary
    └── Home module             Dashboard render, mileage tracker UI
```

### Data schema

Two parallel trip stores for v1/v2 compatibility:

```javascript
// v2 trip (gp_trips_v2)
{
  id:           'trip_20260527_143022',
  startedAt:    '2026-05-27T21:30:22.000Z',  // UTC timestamp
  platform:     'uber',
  tripType:     'rideshare',
  earnings:     { fare: 11.10, tip: 3.00, total: 14.10, tipped: true },
  distance:     { miles: 4.2, method: 'gps' },
  pickupLat:    32.897,   // captured at trip START
  pickupLng:    -117.197,
  pickupZone:   'Sorrento Valley',
  dropoffLat:   32.715,
  dropoffLng:   -117.162,
  startLocation:{ coords: [32.897, -117.197], zone: 'Sorrento Valley' }
}
```

All date filtering uses local timezone (`localDateStr()`) not UTC — a trip at 10 PM Pacific stays on today's date, not rolling to tomorrow.

---

## San Diego coverage

**Venues tracked (242 events):** Petco Park, Snapdragon Stadium, Pechanga Arena, Del Mar Fairgrounds, La Jolla Playhouse, San Diego Convention Center

**36 zones defined** across San Diego County: Airport Corridor, Sorrento Valley, UCSD/UTC, Del Sur, Carmel Valley, Pacific Beach, Mission Beach, Ocean Beach, Mission Valley, Gaslamp, Little Italy, North Park, Hillcrest, La Jolla, Coronado, Chula Vista, El Cajon, Santee and more.

**UCSD calendar integration** filters to in-person events with estimated attendance ≥200 from relevant categories: Arts & Performances, Sports & Recreation, Social, Cultural, Student Life. Academic workshops and virtual events excluded.

---

## Installation

No installation. Open in Chrome on Android, tap menu → Add to Home Screen. The icon opens GigPilot as a PWA — full screen, no browser chrome.

For GPS and airport data to work, the app must be opened from the GitHub Pages URL (HTTPS), not a downloaded HTML file.

---

## Optional: Claude API integration

Without an API key, GigPilot generates rule-based plans from your trip data. With a Claude API key (Anthropic), Today's Plan uses Claude Sonnet to synthesize your trip history, live airport data, SD events, and UCSD events into a natural language shift plan. The Intelligence brief uses Claude Haiku for a 2-3 sentence actionable summary when 5+ trips are logged.

Add your key in Settings → Claude API key.

---

## Data privacy

All trip data stays on your device. Nothing is sent to any server except:
- OpenSky Network (airport flight positions — no personal data)
- Open-Meteo (weather by GPS coordinates)
- calendar.ucsd.edu (public event calendar — read only)
- Anthropic API (if Claude key is configured — trip summary sent for plan generation)

---

## Built by

Tarun Thadani — active Uber/Lyft/DoorDash/UberEats driver, San Diego.
Built in 20 days while driving full shifts.

---

## Roadmap

- **Phase 3:** Native Android APK via Capacitor (background GPS)
- **Phase 4:** Community intelligence — anonymised hotspot sharing across drivers
- **Phase 5:** $4.99–$9.99/month subscription with multi-city support

---

*GigPilot tracks. GigPilot decides.*
