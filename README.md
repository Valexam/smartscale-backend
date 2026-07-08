# SmartScale Backend  
### AI-Assisted Nutrition Tracking for a Voice-Controlled Smart Food Scale

> A backend for an AI-assisted smart food scale that combines barcode lookup, pantry data, voice matching and nutrition tracking.

---

## Overview

**SmartScale** is a smart nutrition-tracking system built around a connected ESP32-S3 food scale, a mobile gateway app and a FastAPI backend.

The goal is simple:

> Make food logging feel less like filling in a spreadsheet and more like using a smart kitchen device.

Instead of manually searching for every product, typing weights and selecting nutrition entries, SmartScale connects:

- a physical food scale
- live weight readings over BLE
- a mobile app
- barcode/product lookup
- a digital pantry
- AI-assisted voice matching
- structured nutrition data

The backend is the public API layer that stores measurements, manages products and pantry items, handles voice-to-pantry matching and exposes the system over HTTPS.

---

## The Problem

Nutrition tracking is powerful, but most apps are annoying to use.

You usually have to:

1. Open an app
2. Search for a product
3. Pick from messy results
4. Manually weigh the food
5. Type the amount
6. Hope the nutrition entry is correct

That friction is why people stop tracking.

SmartScale explores a different workflow:

> Put food on the scale, identify it through barcode or voice, and let the system connect the weight to the right product.

---

## The AI Angle

SmartScale uses AI where it actually improves the user experience: **matching natural language to structured pantry data**.

Example:

```txt
User says: "cereal"
Digital pantry contains: Cheerios, oats, rice, soy milk
System resolves: Cheerios
```

This is not “AI for AI’s sake”.

The AI-assisted layer helps bridge the gap between how people naturally talk about food and how nutrition systems store products.

Instead of forcing the user to say the exact database name, SmartScale can interpret a generic spoken term and match it against the user’s known pantry items.

---

## Core Features

### AI-Assisted Voice Matching

Voice transcripts can be matched against a user’s pantry to select the most likely food item.

Useful for cases like:

- “cereal” → Cheerios
- “milk” → the user’s saved milk product
- “protein powder” → the user’s actual product

### Barcode-Based Product Lookup

The mobile app can scan a barcode and send it to the backend for product lookup and nutrition handling.

### Digital Pantry

The backend supports pantry-style product storage so the system can reason over the user’s actual available products instead of searching a generic database every time.

### Measurement Storage

Weight + product data can be stored as structured measurements for nutrition tracking.

### Public API Layer

The backend exposes the SmartScale system through a FastAPI service with structured endpoints, database persistence and deployment support.

---

## System Architecture

```txt
┌─────────────────────┐
│   ESP32-S3 Scale    │
│                     │
│ - load cell         │
│ - LCD               │
│ - encoder           │
│ - microphone        │
│ - BLE peripheral    │
└──────────┬──────────┘
           │ BLE
           ▼
┌─────────────────────┐
│    Mobile App       │
│                     │
│ - BLE gateway       │
│ - barcode scanner   │
│ - audio forwarding  │
│ - result display    │
└──────────┬──────────┘
           │ HTTPS
           ▼
┌─────────────────────┐
│ SmartScale Backend  │
│                     │
│ - FastAPI           │
│ - Postgres          │
│ - pantry matching   │
│ - product lookup    │
│ - measurements      │
│ - voice endpoints   │
└─────────────────────┘
```

The phone acts as the gateway. The ESP32-S3 handles the physical scale and BLE communication, while the mobile app connects the device to the backend.

---

## Backend Stack

- **Python 3.12**
- **FastAPI**
- **Postgres 16**
- **SQLAlchemy async**
- **Alembic migrations**
- **OpenAI Whisper integration**
- **Docker Compose**
- **Caddy**
- **GitHub Actions**
- **Hetzner deployment**

---

## Example Workflow

### Barcode flow

```txt
1. User places food on the SmartScale
2. Mobile app reads live weight over BLE
3. User scans product barcode
4. App sends barcode + weight to backend
5. Backend resolves product and nutrition data
6. Measurement is stored
```

### Voice flow

```txt
1. User says a food name
2. Audio is captured through the SmartScale / mobile flow
3. Backend receives transcript
4. System matches transcript against the digital pantry
5. Correct pantry item is selected
6. Weight + product can be logged
```

---

## Why This Is Interesting

Most nutrition apps are software-only.

SmartScale combines:

| Layer | Role |
|---|---|
| Embedded hardware | Real-world weighing device |
| BLE | Low-power device communication |
| Mobile app | Gateway, scanner and user interface |
| Backend API | Product, pantry and measurement logic |
| AI | Natural-language pantry matching |
| Deployment | Real hosted API infrastructure |

That makes it more than a CRUD app.

It is a full-stack hardware + mobile + backend + AI system.

---

## Repository Split

SmartScale is split into two repositories:

### `Smart-Scale`

Private monorepo containing:

- ESP32-S3 firmware
- Flutter mobile app
- BLE protocol documentation
- hardware-side architecture
- internal planning
- scraper scaffolding

### `smartscale-backend`

Public backend containing:

- FastAPI service
- Postgres schema
- pantry APIs
- measurement APIs
- product lookup
- voice matching
- deployment configuration

This repository is the public backend half of the system.

---

## Quick Start

```bash
git clone https://github.com/Valexam/smartscale-backend.git
cd smartscale-backend/infra/prod

cp .env.example .env

docker compose up -d postgres
docker compose run --rm migrate
docker compose up -d api

curl http://localhost:8000/v1/healthz
```

For local development without the production Caddy setup, see the development docs.

---

## API Areas

The backend is designed around the main product flows:

- health checks
- device-authenticated requests
- product lookup
- pantry management
- measurement logging
- voice transcript matching
- scrape job handling

---

## Security Model

The backend uses device-key based access for device/API interaction.

The broader SmartScale system keeps the ESP32 as a BLE device and uses the phone as the internet-connected gateway. This avoids forcing the microcontroller to own cloud authentication, HTTPS complexity and product lookup directly.

Future versions may support direct ESP32-to-cloud onboarding, but the current architecture keeps the first version simpler and easier to debug.

---

## Current Status

Implemented / merged:

- local scale firmware
- BLE link
- phone gateway to backend
- macros + product lookup
- scraper v0
- digital pantry
- cloud voice pipeline
- scale-side audio plumbing
- wake-on-voice foundation
- LCD result display
- encoder confirm/cancel flow
- mobile UI refresh
- Hetzner API deployment
- backend extracted into public repository

Future:

- real user authentication
- standalone ESP32-to-cloud mode
- deeper scraper orchestration
- more advanced pantry intelligence
- improved product disambiguation

---

## Design Goals

SmartScale is built around a few product principles:

- logging should be faster than manual nutrition tracking
- users should not need to remember exact product names
- pantry data should make food selection smarter
- hardware should remove friction, not add it
- AI should assist selection, not hallucinate nutrition facts
- the phone should act as a practical gateway between embedded hardware and the cloud

---

## What This Demonstrates

This project demonstrates practical experience across:

- embedded systems
- BLE communication
- mobile gateway architecture
- backend API design
- async Python services
- database modeling
- deployment
- product-data workflows
- AI-assisted user interaction
- end-to-end system design

---

## One-Line Summary

**SmartScale is an AI-assisted smart food scale system that connects embedded hardware, mobile BLE, FastAPI and pantry-based voice matching to make nutrition tracking faster and more natural.**
