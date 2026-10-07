# Pstryk G12W – Home Assistant

Niestandardowa integracja Home Assistant analizująca godzinowe zużycie z Pstryk i klasyfikująca je według ustawionych godzin szczytu. Zawiera konfigurację przez UI, polskie święta, strefę `Europe/Warsaw`, uwzględnia zmianę czasu oraz pobiera dane zużycia i kosztu.

> **Warunki API:** darmowy klucz Pstryk jest przeznaczony do prywatnego, niekomercyjnego użytku. Regulamin przewiduje limit 3 zapytań na godzinę na obciążający endpoint. Integracja odpytuje dwa endpointy co 30 minut (2 razy na godzinę każdy). Używaj klucza wyłącznie zgodnie z aktualnym regulaminem Pstryk.

## Instalacja przez HACS

1. W HACS wybierz **Integracje → ⋮ → Repozytoria niestandardowe**.
2. Opublikuj zawartość tego katalogu jako repozytorium GitHub i wpisz URL repozytorium w HACS; wybierz kategorię **Integration**.
3. Zainstaluj **Pstryk G12W Energy Analysis** i uruchom ponownie Home Assistant.
4. W **Ustawienia → Urządzenia i usługi → Dodaj integrację** wyszukaj „Pstryk G12W”.
5. Wklej klucz API.

Po utworzeniu wpisu opcje taryfy znajdziesz w **Ustawienia → Urządzenia i usługi → Pstryk G12W → Konfiguruj**.

### Klucz i identyfikator

Klucz wygenerujesz w aplikacji Pstryk: **Konto → Urządzenia i integracje → Generuj klucz API**. Pstryk pokazuje go tylko raz; skopiuj go w bezpieczne miejsce. Klucz jest przypisany do miernika, więc integracja nie prosi osobno o identyfikator licznika. Home Assistant przechowuje sekret w swoim wpisie konfiguracji, formularz nie ujawnia go ponownie, a diagnostyka go nie eksportuje. Integracja nie szyfruje osobno pliku `.storage`; zabezpiecz katalog konfiguracji i kopie zapasowe Home Assistant uprawnieniami systemu oraz szyfrowaniem dysku/backupów.

## Taryfa

Domyślnie:

- dni robocze: szczyt `06:00-13:00,15:00-22:00`;
- soboty i niedziele: brak godzin szczytu;
- święta państwowe w Polsce: cały dzień poza szczytem;
- strefa: `Europe/Warsaw`.

Przedziały są lokalnymi godzinami ściennymi; godzina końcowa jest wyłączna. Format: `HH:MM-HH:MM,HH:MM-HH:MM`. Działa też przedział przez północ, np. `22:00-06:00`. Lista dni świątecznych zawiera stałe polskie święta oraz Wielkanoc, Poniedziałek Wielkanocny i Boże Ciało. Od 2025 r. uwzględnia także 24 grudnia.

Godziny są domyślną konfiguracją G12W, a nie gwarancją zgodności z każdą umową dystrybucyjną. Ustaw harmonogram zgodny z własną taryfą i operatorem.

## Encje

Integracja tworzy sensory energii za dziś i bieżący miesiąc, udział procentowy szczytu/pozaszczytu oraz kwoty z endpointu kosztowego Pstryk:

- `sensor.pstryk_g12w_zuzycie_dzis_w_szczycie`
- `sensor.pstryk_g12w_zuzycie_dzis_poza_szczytem`
- `sensor.pstryk_g12w_udzial_szczytu_dzis`
- `sensor.pstryk_g12w_udzial_poza_szczytem_dzis`
- `sensor.pstryk_g12w_zuzycie_w_szczycie_w_tym_miesiacu`
- `sensor.pstryk_g12w_zuzycie_poza_szczytem_w_tym_miesiacu`
- sensory udziału procentowego dla bieżącego miesiąca;
- koszt całkowity dziś i w miesiącu oraz koszt w obu okresach taryfowych za dziś i bieżący miesiąc.

Kwoty pochodzą z Pstryk `energy-cost` i są przypisywane do taryfy na podstawie znacznika godziny. Nie są wyliczane z samej ceny rynkowej ani z taryfy dystrybucyjnej. Pstryk może publikować odczyty z opóźnieniem; brak danych jest pokazany jako niedostępna wartość.

## API i limity

Integracja korzysta z:

- `GET https://api.pstryk.pl/integrations/meter-data/energy-usage/` z `resolution=hour` (kWh);
- `GET https://api.pstryk.pl/integrations/meter-data/energy-cost/` z `resolution=hour` (PLN).

Okno zapytania podawane jest w UTC, a `for_tz=Europe/Warsaw` ułatwia agregację kalendarzową. Autoryzacja wykorzystuje indywidualny klucz API w nagłówku `Authorization`; obsługiwany jest format surowego klucza oraz `Bearer`, bo oba pojawiają się w publicznych przykładach integracji. Błędy autoryzacji, HTTP 429, błędy serwera, timeouty i błędne odpowiedzi są raportowane przez mechanizm Home Assistant. Żadna odpowiedź ani klucz nie są logowane.

API Pstryk nie gwarantuje SLA. Integracja przechowuje ostatnie dane w pamięci koordynatora podczas pracy HA, ale nie tworzy osobnego trwałego archiwum. Historia encji zależy od ustawień Recorder Home Assistant.

## Przykłady

Automatyzacja powiadamiająca, gdy dzisiejsze zużycie w szczycie przekroczy 5 kWh:

```yaml
alias: Pstryk – wysokie zużycie w szczycie
triggers:
  - trigger: numeric_state
    entity_id: sensor.pstryk_g12w_zuzycie_dzis_w_szczycie
    above: 5
actions:
  - action: notify.notify
    data:
      message: >-
        Zużycie w szczycie wynosi
        {{ states('sensor.pstryk_g12w_zuzycie_dzis_w_szczycie') }} kWh.
mode: single
```

Prosta karta encji:

```yaml
type: entities
title: Pstryk – zużycie energii
entities:
  - sensor.pstryk_g12w_zuzycie_dzis_w_szczycie
  - sensor.pstryk_g12w_zuzycie_dzis_poza_szczytem
  - sensor.pstryk_g12w_udzial_szczytu_dzis
  - sensor.pstryk_g12w_koszt_energii_dzis_wg_pstryk
  - sensor.pstryk_g12w_zuzycie_w_szczycie_w_tym_miesiacu
  - sensor.pstryk_g12w_zuzycie_poza_szczytem_w_tym_miesiacu
```

## Rozwój i testy

Testy czystej logiki taryfowej uruchomisz z katalogu repozytorium przez `pytest`. Integracja nie wymaga dodatkowych zależności poza Home Assistant.

## Źródła API

- [Regulamin otwartego API Pstryk](https://pstryk.pl/regulamin-api)
- [Pstryk: klucze API w aplikacji](https://www.pstryk.pl/blog/co-nowego-w-aplikacji-pstryk-2-klucze-api)
- [Biblioteka Pstryk JS z endpointami i polami odpowiedzi](https://github.com/ground-engineering/pstryk-js)
- [Swagger Pstryk](https://api.pstryk.pl/swagger/) (obecnie ekran logowania)
