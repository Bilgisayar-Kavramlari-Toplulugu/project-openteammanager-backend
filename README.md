# 🧭🤝 Open Team Manager

<div align="center">

[![GitHub](https://img.shields.io/badge/GitHub-Bilgisayar%20Kavramlari%20Toplulugu-181717?style=flat-square\&logo=github\&logoColor=white)](https://github.com/Bilgisayar-Kavramlari-Toplulugu/project-openteammanager-backend)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?style=flat-square\&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square\&logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square\&logo=postgresql\&logoColor=white)](https://www.postgresql.org/)


**Part of [Open Team Manager](docs/Project-Definition.md) - [Bilgisayar Kavramları Topluluğu](https://github.com/Bilgisayar-Kavramlari-Toplulugu)**

</div>

---

<details open>
<summary><strong>🇹🇷 Türkçe</strong></summary>

<br>

> **ÖNEMLİ:** Bu repository **Open Team Manager** projesinin bir parçasıdır. Proje hakkında detaylı bilgi için [`docs/Project-Definition.md`](docs/Project-Definition.md) dosyasına bakın.

## 📖 Hakkında

<!-- Bu repository'nin ne yaptığını buraya yazın -->
Open Team Manager, topluluk projelerini, görevleri ve ekip üyelerini takip etmek için tasarlanmış açık kaynaklı bir proje yönetim sistemidir. Koordinatörler proje açar, üyeler görev alır, ilerleme otomatik takip edilir. Tamamen topluluk tarafından, topluluk için inşa ediliyor.

Temel Özellikler

- 🗂️ Proje oluşturma, kategori bazlı ayırma ve görev yönetimi
- 📋 Kanban ve Gantt panoları ile görselleştirilmiş ilerleme
- 👥 Ekip üyesi yönetimi, rol ve izin kontrolü
- 📊 Otomatik ilerleme raporları ve aktivite logları
- 🔍 Tarih ve öncelik bazlı filtreleme
  
## 🚀 Kurulum

### Gereksinimler

- Frontend:       Next.js 16, TypeScript, Tailwind CSS, shadcn/ui
- BackendPython:  3.12, FastAPI, SQLAlchemy
- Veritabanı:     PostgreSQL 16, Redis 7
- Altyapı:        Docker, GitHub Actions

### Başlangıç

```bash
git clone https://github.com/Bilgisayar-Kavramlari-Toplulugu/project-openteammanager-backend.git
cd project-openteammanager-backend

# Ortam Değişkenlerini Ayarla
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

# Docker ile Başlat
docker compose up --build
docker compose exec backend alembic upgrade head

# Tamamlanınca servislerin durumunu kontrol et
docker compose ps

# örnek çıktı:
backend    running   :8000
frontend   running   :3000
db         running   :5432

# Veritabanını Hazırla - migration çalıştır (kod içindeki tablo tanımlarını okuyup veritabanına uygular)
docker compose exec backend alembic upgrade head

# Çalıştığını Doğrula
# frontend : http://localhost:3000
# backend : http://localhost:8000
# API endpoint'leri : http://localhost:8000/docs

```

## 💻 Kullanım

```bash
# Uygulamayı çalıştırmak için tüm servisleri başlat
docker compose up -d

##### Her çalışma oturumunda servisleri başlatman yeterli

docker compose up       # Tüm servisleri başlatır
docker compose up -d    # Arka planda başlatır, terminal serbest kalır.
docker compose down     # Bitince durdur - tüm servisleri durdurur ve container'ları siler
docker compose logs -f backend    # backend loglarını canlı izle
docker compose logs -f frontend   # frontend loglarını canlı izle

```

## 📁 Proje Yapısı

```
Monorepo Yapısı:

open-team-manager/
├── frontend/
├── backend/
│   └── app/
├── docker-compose.yml      # Tüm stack buradan yönetilir
├── .env.example
└── README.md

------------------------------------
Backend Repo Yapısı:

open-team-manager-backend/
├── app/
│   ├── main.py                  # FastAPI uygulama girişi
│   ├── config.py                # Pydantic Settings
│   ├── database.py              # Async SQLAlchemy engine
│   ├── dependencies.py          # get_db, get_current_user
│   ├── models/                  # SQLAlchemy ORM modelleri
│   │   ├── user.py
│   │   ├── project.py
│   │   └── task.py
│   ├── schemas/                 # Pydantic request/response
│   │   ├── user.py
│   │   └── project.py
│   ├── routers/                 # API endpoint grupları
│   │   ├── auth.py
│   │   ├── projects.py
│   │   ├── tasks.py
│   │   ├── members.py
│   │   └── reports.py
│   ├── services/                # İş mantığı
│   │   ├── auth_service.py
│   │   ├── task_service.py
│   │   └── report_service.py
│   ├── core/
│   │   ├── security.py          # JWT, bcrypt
│   │   ├── permissions.py       # Yetki kontrolü
│   │   └── websocket.py         # WS bağlantı yönetimi
│   └── workers/
│       ├── celery_app.py
│       └── tasks.py             # Arka plan görevleri
├── migrations/                  # Alembic
├── tests/
├── .env.example                 # docker-compose buraya taşındı
├── requirements.txt
└── README.md

```
## Teknik Mimari

```bash
Kullanıcı (Tarayıcı)
        │
        │ HTTP
        ▼
┌─────────────────────────┐
│     Next.js 15          │
│     Frontend            │
│     localhost:3000      │
└───────────┬─────────────┘
            │ REST API
            ▼
┌─────────────────────────┐
│     FastAPI             │
│     Backend             │
│     localhost:8000      │
└──────┬──────────┬───────┘
       │          │
       ▼          ▼
┌──────────┐  ┌──────────┐
│PostgreSQL│  │  Redis   │
│  :5432   │  │  :6379   │
└──────────┘  └────┬─────┘
                   │
                   ▼
            ┌──────────────┐
            │    Celery    │
            │    Worker    │
            └──────────────┘

```

## 🧪 Test

```bash
# Testleri çalıştır
docker compose exec backend pytest

# Tek dosya
docker compose exec backend pytest tests/test_tasks.py

# Tek test
docker compose exec backend pytest tests/test_tasks.py::test_create_task

# Coverage raporu
docker compose exec backend pytest --cov=app --cov-report=term-missing

# Frontend
docker compose exec frontend npm run test
docker compose exec frontend npm run test -- --watch

# Backend
docker compose exec backend ruff check .
docker compose exec backend ruff check --fix .   # otomatik düzelt
docker compose exec backend ruff format .        # biçimlendir

# Frontend
docker compose exec frontend npm run lint
docker compose exec frontend npm run lint -- --fix
docker compose exec frontend npm run type-check
```

## Branch Stratejisi

| Branch | Amaç |
|--------|------|
| `main` | Production — her zaman kararlı |
| `develop` | Aktif geliştirme — PR'lar buraya açılır |
| `feature/otm-<no>-<açıklama>` | Yeni özellik |
| `fix/otm-<no>-<açıklama>` | Hata düzeltme |
| `hotfix/otm-<no>-<açıklama>` | Acil production düzeltmesi |
| `chore/<açıklama>` | Bağımlılık, config güncellemesi |

**Kurallar:** `main` ve `develop`'a doğrudan push yapılamaz. Her değişiklik `feature/*` veya `fix/*` branch'inden PR ile gelir, en az 1 onay gerekir.

## 🤝 Katkıda Bulunma

Her seviyeden katkı memnuniyetle karşılanır
  — kod, dokümantasyon, hata raporu, tasarım önerisi.

Katkıda bulunmak için lütfen [`CONTRIBUTING.md`](.github/CONTRIBUTING.md) dosyasını inceleyin.


## 📚 Dokümantasyon

- [Proje Tanımı](docs/Project-Definition.md)
- [Mimari Genel Bakış](docs/Architecture-Overview.md)
- [Geliştirme Akışı](docs/Development-Workflow.md)

## 📄 Lisans

Bu proje MIT Lisansı ile lisanslanmıştır - detaylar için [LICENSE](LICENSE) dosyasına bakın.

---

**Proje Lideri:** [@hakanceran64](https://github.com/hakanceran64)

</details>

<details>
<summary><strong>🇬🇧 English</strong></summary>

<br>

> **IMPORTANT:** This repository is part of **Ekip yönetimini basitleştir, verimliliği artır!** project. See [`docs/Project-Definition.md`](docs/Project-Definition.md) for details.

## 📖 About

<!-- Describe what this repository does -->

## 🚀 Installation

### Requirements

- List required tools here

### Getting Started

```bash
git clone https://github.com/Bilgisayar-Kavramlari-Toplulugu/project-openteammanager-backend.git
cd project-openteammanager-backend

# Add installation steps here
```

## 💻 Usage

```bash
# Add command to run the application
```

## 📁 Project Structure

```
project-openteammanager-backend/
├── src/          # Source code
├── tests/        # Tests
├── docs/         # Documentation
└── README.md     # This file
```

## 🧪 Testing

```bash
# Add test commands here
```

## 🤝 Contributing

Please see [`CONTRIBUTING.md`](.github/CONTRIBUTING.md) for contribution guidelines.

## 📚 Documentation

- [Project Definition](docs/Project-Definition.md)
- [Architecture Overview](docs/Architecture-Overview.md)
- [Development Workflow](docs/Development-Workflow.md)

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

---

**Project Lead:** [@hakanceran64](https://github.com/hakanceran64)

</details>
