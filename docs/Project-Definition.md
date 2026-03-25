# Open Team Manager
## Project Definition & Scope
Gönüllü Topluluk Projesi — Bilgisayar Kavramları Topluluğu

### 1. Proje Amacı
Open Team Manager, yazılım topluluklarının ve küçük ekiplerin proje ve görev yönetimini tek bir açık kaynak platform üzerinden yürütmesini sağlayan bir web uygulamasıdır.
Kullanıcılar; organizasyon oluşturabilir, projelere üye ekleyebilir, görevleri Kanban board üzerinde yönetebilir, sprint planlayabilir ve ilerlemeyi raporlar aracılığıyla takip edebilir.
Uygulama, Docker ile kolayca kurulabilecek ve toplulukların kendi altyapısında çalıştırabileceği şekilde tasarlanmıştır.

### 2. Ana Hedefler
| # | Hedef | Ölçüt |
|---|---|---|
| 1 | Organizasyon yönetimi: kullanıcılar organizasyon oluşturabilmeli, üye davet edebilmeli ve rol atayabilmeli | Organizasyon CRUD ve üyelik endpoint'leri çalışıyor |
| 2 | Görev yönetimi: görevler oluşturulabilmeli, atanabilmeli ve Kanban board üzerinde sürükle-bırak ile taşınabilmeli | Kanban board tüm statü geçişlerini destekliyor |
| 3 | Sprint planlaması: görevler sprinte eklenip çıkarılabilmeli ve kapasite takip edilebilmeli | Sprint CRUD ve sprint-task ilişkisi çalışıyor |
| 4 | Gerçek zamanlı güncelleme: görev değişiklikleri anlık olarak yansımalı | Aynı projede açık iki tarayıcıda eş zamanlı güncelleme görünüyor |
| 5 | Raporlama: burndown ve velocity grafikleri sprint verisiyle üretilebilmeli | Rapor endpoint'leri test edilebilir veri döndürüyor |
| 6 | Kolay kurulum: uygulama tek komutla ayağa kalkmalı | docker compose up -d sonrası sağlık kontrolü geçiyor |

### 3. Kapsam Dahilinde
#### 3.1 Kimlik ve Erişim Yönetimi
* E-posta ve şifre ile kayıt ve giriş
* GitHub OAuth ile sosyal giriş
* Rol tabanlı yetki sistemi: owner / admin / member / viewer
* E-posta doğrulama akışı

#### 3.2 Organizasyon ve Proje Yönetimi
* Organizasyon oluşturma, güncelleme, silme (soft delete)
* Organizasyona üye davet etme ve rol yönetimi
* Proje oluşturma, güncelleme, arşivleme
* Proje bazlı üyelik ve yetki seti

#### 3.3 Görev Yönetimi
* Görev oluşturma, güncelleme, silme (soft delete)
* Alt görev desteği (hiyerarşik yapı)
* Görev durumları: Yapılacak / Devam Ediyor / İncelemede / Tamamlandı / İptal
* Öncelik seviyeleri: Kritik / Yüksek / Orta / Düşük
* Görev tipleri: Görev / Bug / Özellik / Epic / Hikaye
* Atama, etiket, son tarih, tahmini süre ve story point
* Dosya eki yükleme (maksimum 50 MB)
* Görev yorumları ve yorum thread'i

#### 3.4 Görselleştirme ve Planlama
* Kanban board (sürükle-bırak ile statü değişimi)
* Gantt chart (başlangıç/bitiş tarihlerine göre görsel çizelge)
* Sprint yönetimi: oluşturma, görev atama, kapasite takibi
* Filtreleme: durum, öncelik, atanan kişi, etiket, tarih
* Arama: başlık ve açıklamada metin arama

#### 3.5 Raporlama
* Sprint burndown grafiği
* Velocity grafiği (sprint karşılaştırmalı)
* Kişisel dashboard: bana atanan görevler, son aktivite, sprint özeti

#### 3.6 Gerçek Zamanlı ve Bildirimler
* WebSocket ile Kanban board canlı güncelleme
* In-app bildirim sistemi (görev ataması, yorum bildirimi)
* Aktivite geçmişi (denetim izi)

#### 3.7 Altyapı
* Docker Compose ile geliştirme ortamı kurulumu
* Alembic ile veritabanı migrasyon yönetimi
* GitHub Actions CI/CD pipeline (lint, test, build)
* MinIO dosya depolama (lokal) / AWS S3 (prod)

### 4. Kapsam Dışında
Aşağıdaki özellikler v1.0'a dahil değildir. Topluluk tarafından ilerleyen fazlarda değerlendirilebilir.

| Konu | Neden Dışarıda? |
|---|---|
| Mobil uygulama (iOS / Android) | Ayrı bir proje kapsamı gerektirir |
| Gerçek zamanlı video/sesli toplantı | Kapsam ve kaynak açısından orantısız büyüme yaratır |
| Harici takvim entegrasyonu (Google Calendar, Outlook) | Ayrı OAuth kapsamı ve uzun vadeli bakım yükü |
| AI destekli görev önerisi veya otomatik önceliklendirme | Ayrı bir araştırma fazı gerektirir |
| Çoklu dil desteği (i18n) | v2.0 hedefi; v1.0'da Türkçe + İngilizce UI yeterli |
| Enterprise SSO (SAML, LDAP) | Hedef kitle küçük/orta topluluklar |
| Ücretli plan / ödeme sistemi | Proje açık kaynak ve ücretsizdir |
| Kubernetes production deployment | v1.0 sonrası değerlendirilecek |

### 5. Teknik Kısıtlar
| Alan | Karar |
|---|---|
| Veritabanı | PostgreSQL 16 — MySQL, SQLite veya NoSQL kullanılmaz |
| ORM | SQLAlchemy 2 async — ham SQL yalnızca performans kritik sorgularda |
| Kimlik doğrulama | JWT + HttpOnly Cookie — session tabanlı auth kullanılmaz |
| Dosya depolama | MinIO (lokal) / AWS S3 (prod) — maksimum 50 MB/dosya |
| Real-time | WebSocket (native) — Socket.IO veya SSE tercih edilmez |
| Kod stili | Backend: ruff + black; Frontend: ESLint + Prettier |

### 6. Yüksek Seviye Zaman Çizelgesi
| Faz | Süre | Ana Çıktı |
|---|---|---|
| Faz 1 — Temel | 4 Hafta | Auth, Org/Proje CRUD, Görev yönetimi, Kanban board |
| Faz 2 — Ekip & İş Akışı | 3 Hafta | Üye yönetimi, roller, yorumlar, dosya ekleri, aktivite logu |
| Faz 3 — Görselleştirme | 3 Hafta | Gantt, filtreler, WebSocket canlı güncelleme, bildirimler |
| Faz 4 — Raporlama | 2 Hafta | Burndown/velocity grafikleri, Celery arka plan işleri |
| Faz 5 — Optimizasyon | 2 Hafta | Test kapsamı, CI/CD pipeline, performans, v1.0 release |

Toplam: 14 hafta — Gönüllülük temposuna göre sprint süreleri gerektiğinde uzatılabilir.
Son güncelleme: Mart 2026 — Her faz sonunda bu dokümanın gözden geçirilmesi önerilir.
