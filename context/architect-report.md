# Raport architektoniczny: moduł 4 (10xArchitect)

Stan na 2026-11-04. L2–L5 to lekcje modułu. Liczby pochodzą z artefaktów; nic nie zbudowano ani nie uruchomiono.

## 1. Opisane projekty

Jedno repozytorium: **Godot Engine** (fork `Hornster/godot-tests`), silnik gier w C++ (SCons) z edytorem napisanym w samym silniku. Skala: ok. 1,7 mln LOC C++ i ok. 200 tys. LOC w siedmiu innych językach, 371 autorów. Innych projektów nie użyto. Kod silnika jest identyczny we wszystkich snapshotach (`git diff`).

| Lekcja | Artefakt (w `context/`) | Repo | Snapshot |
|---|---|---|---|
| L2 | `map/repo-map.md` | Godot | `6765a18ca8` |
| L3 | `changes/material-resources-flow-analysis/research.md` | Godot | `0f30f7d853` |
| L4 | `changes/refactor-opportunities/plan.md` | Godot | `a27e041bc3` |
| L5 | `domain/01-domain-distillation.md`, `02-invariant-aggregate-refactor.md`, `03-anti-corruption-layer.md` (dalej 01, 02, 03) | Godot | `a27e041bc3` |

## 2. Mapa projektu (L2)

- **Strefy ryzyka (6).** Tu kluczowe: zapis i odczyt scen (zmiana zapisu właściwości cicho psuje stare pliki), materiały i cząsteczki (reverty #115163, #116140, #118373), dwa ręcznie utrzymywane renderery, GLES3 i RD (57 % commitów GLES3 zmienia też RD).
- **Lokalne centra.** `class_db.h`: 797 includerów we wszystkich 9 warstwach; `editor_node.h`: 226 (god object). `scene/resources` leży w `scene/`, a działa poniżej `servers/`.
- **Entry pointy.** `main/main.cpp` (`Main::setup → setup2 → start → iteration`); 44 z 59 modułów podłącza się tylko przez `register_types.cpp`.
- **Unknowns.** Połączenia runtime (ClassDB, sygnały, singletony) i generowane API C# nie mają grafu: to niewiadoma, nie „brak sprzężenia”. Testy dotykają ok. 3 % commitów.

## 3. Analiza ficzera (L3)

**Przepływ:** edycja zasobów materiałów; łączy strefy zapisu i odczytu, materiałów oraz rendererów. Powód (notatki): zasoby to fizyczna podstawa pracy użytkownika, a ich błąd grozi utratą danych.

**Overview.** Wejściem jest edycja w inspektorze, która przez UndoRedo i `Object::set` trafia do settera materiału. Stan zmienia się dwoma kanałami: wartość (np. `albedo_color`) idzie od razu do `RenderingServer` (52 wywołania `_material_set_param`), a klucz shadera (feature, flaga, tekstura; 26 setterów) trafia na listę `dirty_materials`, opróżnianą w idle callbacku przez wygenerowanie shadera lub pobranie go ze współdzielonej `shader_map`. Do edytora wraca obraz przez wspólny uchwyt RID i odświeżona lista właściwości. Zapis to refleksja po właściwościach różnych od domyślnych, a odczyt to `ClassDB::instantiate` plus `Object::set`, bez migracji wersji formatu.

| Technical debt (ID z researchu) | Dowód (ast-grep) | Skutek |
|---|---|---|
| **Luka testowa** (D8 „dziury w testach”) | 0 odwołań w `tests/` do konkretnych klas materiałów; asercje tylko w 3 nagłówkach glTF (uściśla „0 referencji” z mapy) | Weryfikacja ręczna; informacją zwrotną są reverty |
| **Kruche sprzężenie** (D1 „trzy kopie cache'a shaderów”) | 3 idle flushe; tylko BaseMaterial3D opróżnia listę poza blokadą | Poprawka w jednej kopii nie trafia do innych |
| **Blast radius** (D2 „kontrakt tekstowy shaderów”) | `material.h`: 37 includerów, 150 w dwóch skokach; 31 z 32 render mode'ów nazwanych we wszystkich rendererach, bez wymuszenia | Fix tylko w `material.cpp` cofnięto (#115163); ponowna wersja: 9 plików |

Metoda: ast-grep 0.50.0, `--lang cpp`, `*.h` jako C++; z 43 twierdzeń 20 uściślono, 2 obalono.

## 4. Plan refaktoryzacji (L4)

**Status: plan, nie wdrożenie.** Wykonano 0 z 83 kroków. BRAK artefaktu: `baseline.md`, wyniki testów i CI. „Implementation” w commicie `a27e041bc3` to pomyłka (notatki). Każdy obszar zaczyna się od testów charakteryzujących; zachowanie się nie zmienia.

- **C1, wspólny cache shaderów:** szablon `generated_shader_cache.h` dla BaseMaterial3D i ParticleProcessMaterial, bez zmiany zakresów blokad.
- **C8, jedno źródło argumentów `get_material_for_2d`:** `Material2DParams` i wspólne mapowanie alpha-cut dla Sprite3D, Label3D i shader bakera (prekompilacja przy eksporcie).
- **C10, odcięcie `navigation_server_3d.h` od `scene/`:** singleton `NavigationDebug3D` przejmuje kolory, przełączniki, 27 ustawień i 15 materiałów debugowych.

**Świadomie NIE:** migracja i naprawa CanvasItemMaterial (tylko testy); ujednolicanie polityk blokad i inicjalizacji; nowe warianty w bakerze; NavigationServer2D; zmiany nazw i wartości domyślnych sygnałów oraz ustawień; kandydaci C2–C7 i C9.

Fazy 2–12 auto: build, testy celowane, pełny zestaw. Szablon = build bez 3D; doctool = diff dokumentacji.

| # | Faza | Auto, m.in. | Ręcznie |
|---|---|---|---|
| 1 | Toolchain, baseline | build, testy, fork CI | odsianie błędów CI z forka |
| 2 | C1: testy cache'a | format | celowe zepsucie refcountu |
| 3 | C1: cache + ParticleProcessMaterial | grep | stan blokad wywołań |
| 4 | C1: BaseMaterial3D | grep, CI (TSan, ASan) | blokady, edycja na żywo |
| 5 | C8: testy alpha-cut | format | celowa zamiana gałęzi |
| 6 | C8: `Material2DParams`, węzły | grep, doctool | wygląd trybów alpha-cut |
| 7 | C8: baker | grep, CI | liczba wariantów shaderów |
| 8 | C10: testy debugu i sygnałów | format | przegląd liczby emisji |
| 9 | C10: odcięcie include'a | szablon, grep | brak |
| 10 | C10: fasada `NavigationDebug3D` | szablony, doctool | brak |
| 11 | C10: migracja wywołań | szablony, grep | wizualizacje debugu |
| 12 | C10: przeniesienie stanu | doctool, API GDExtension, CI | Project Settings, stare klucze |

## 5. Domena wg DDD (L5)

**Ubiquitous language** (01). **Material:** zasób na dysku albo rekord renderera (RID); jedno słowo, dwa konteksty. **MaterialKey i `shader_map`:** tożsamość wariantu shadera i współdzielony cache; mechanizm celu G2 („płacisz tylko za to, czego używasz”), którego dokumentacja nie nazywa. **Default value:** także baza zapisu, bo wartość równa domyślnej nie trafia do pliku.

**Rozjazdy.** M3 (CPUParticles): dokumentacja obiecuje „same functionality”, a kod celowo ma 3 flagi wobec 6. M6 (nieznane nazwy): `StandardMaterial3D::_set` zwraca `true`, choć kontrakt `Object` wymaga `false`. PBR jest w dokumentacji, w kodzie go nie ma. BRAK artefaktu: PRD.

**Niezmiennik #1: I1, integralność presetu stencil** (02). Przy OUTLINE lub XRAY `next_pass` należy wyłącznie do tego materiału, a jego ustawienia wynikają z właściciela (priorytet = właściciel + 1), także po odczycie. **Agregat:** korzeń `BaseMaterial3D`, potomek `StandardMaterial3D` z meta `_stencil_owned`. Regułę sprawdza tylko `set_stencil_mode`; omijają ją cztery wejścia (m.in. `set_render_priority`, `duplicate()`), a load loguje błąd i działa dalej. Ranking w 01 na #1 stawia inny agregat, A4 Generated Shader Cache, pokryty już przez C1.

**Anti-Corruption Layer** (03, propozycja). Przecieka **Clipper2** (operacje na poligonach) mimo wrappera `Geometry2D`: **4 pliki poza wrapperem w 3 warstwach** (`scene` ×2, `editor`, `modules`), a flaga `CLIPPER2_ENABLED` sięga nagłówka w czwartej, `servers`. Precyzja zależy od miejsca (5, 2 lub 1), a opcji `builtin_clipper2=no` kod nie potrafi zrealizować. Cel: port `PolygonClipper2D`; bibliotekę znają tylko adapter i kodek.

## 6. Decyzje, które należą do mnie

Wybór Godota i zawężenie analizy do materiałów to moje decyzje, oparte na intensywnym używaniu silnika. AI uszeregowało kandydatów; ranking C1 → C8 → C10 przyjmuję, bo C8 już dryfuje, a C10 rozprzęga moduły. Zakres C10 to moja propozycja: serwer nawigacji nie powinien być właścicielem kolorów (`plan-brief.md`). AI wskazało cache shaderów, a potem preset stencil; rozstrzygam: stencil zaraz po cache'u, bo jest najszerzej rozlany (6 warstw) i egzekwowany w jednym miejscu. Nominację Clipper2 potwierdza własne uruchomienie ast-grep (4 include'y), a otwarte decyzje projektowe z 02 i 03 pozostają rekomendacjami AI (BRAK artefaktu z ich rozstrzygnięciem).
