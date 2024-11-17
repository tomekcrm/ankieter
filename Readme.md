# Dokumentacja Techniczna Systemu Analizy Wyników Ankiet

> **Uwaga:** Klucze używane w systemie **nie są usuwane**, baza danych jest **czysta**, co ułatwia korzystanie nauczycielom. Obecnie system **nie jest nigdzie hostowany**. Jeśli ktokolwiek chciałby go uruchomić na serwerze, zaleca się zmianę wszystkich kluczy oraz dodanie odpowiednich środków bezpieczeństwa.

## Spis Treści
1. Wprowadzenie
2. Przegląd Systemu
3. Metodyka Analizy Wyników Ankiet
   - Przetwarzanie Danych
   - Obliczanie Średniej Ważonej
   - Obliczanie Procentu Wypełnionych Ankiet
   - Kryteria Filtracji Danych
4. Struktura Danych
   - Kluczowe Zmienne
5. Architektura Aplikacji
6. Interfejs Użytkownika
   - Tabela 3.1
   - Tabela 3.2
   - Tabela 3.3
   - Tabela 3.4
   - Tabela 2.1
   - Tabela 2.2
7. Analiza Wyników
8. Bezpieczeństwo i Zarządzanie Danymi
9. Instalacja i Konfiguracja
10. Przykładowe Formuły Matematyczne
11. Zakończenie

## Wprowadzenie
Niniejsza dokumentacja techniczna opisuje System Analizy Wyników Ankiet, który został zaprojektowany w celu przetwarzania, analizy i wizualizacji zagregowanych wyników ankiet edukacyjnych eksportowanych z systemu USOS Ankieter. System ten umożliwia instytucjom edukacyjnym ocenę efektywności dydaktycznej nauczycieli oraz identyfikację obszarów wymagających poprawy.

## Przegląd Systemu
System Analizy Wyników Ankiet jest aplikacją webową opartą na frameworku Flask, która umożliwia użytkownikom:

- **Przesyłanie Danych**: Importowanie plików CSV zawierających zagregowane wyniki ankiet.
- **Przechowywanie Danych**: Bezpieczne przechowywanie danych w bazie SQLite.
- **Analizę Danych**: Przeprowadzanie obliczeń statystycznych, takich jak średnie ważone i procent wypełnionych ankiet.
- **Prezentację Danych**: Wyświetlanie wyników w formie przejrzystych tabel i analiz, co ułatwia interpretację danych.

System zapewnia interaktywny interfejs użytkownika, umożliwiający łatwe nawigowanie pomiędzy różnymi raportami i analizami.

## Metodyka Analizy Wyników Ankiet
### Przetwarzanie Danych
- **Importowanie Danych**: Użytkownik przesyła plik CSV zawierający zagregowane wyniki ankiet eksportowane z systemu USOS Ankieter. System sprawdza poprawność formatu pliku oraz unikalność poprzez obliczenie hash MD5, aby zapobiec duplikacji danych.
- **Przechowywanie Danych**: Dane z pliku CSV są mapowane do odpowiednich pól w bazie danych SQLite. Każdy rekord odpowiada jednemu pytaniu w ankiecie dotyczącym konkretnego nauczyciela i przedmiotu.

### Obliczanie Średniej Ważonej
Średnia ważona jest kluczowym wskaźnikiem oceny efektywności dydaktycznej nauczycieli. Pozwala ona uwzględnić różną liczbę odpowiedzi na poszczególne pytania, co zwiększa wiarygodność wyników.

**Wzór Matematyczny**:

\[
\bar{x}_w = \frac{\sum_{i=1}^n (x_i \times w_i)}{\sum_{i=1}^n w_i}
\]

Gdzie:
- \(\bar{x}_w\) – Średnia ważona.
- \(x_i\) – Średnia ocena dla pytania \(i\).
- \(w_i\) – Liczba ankiet wypełnionych dla pytania \(i\).
- \(n\) – Liczba pytań uwzględnionych w obliczeniach.

**Implementacja**:
1. **Sumowanie Ważonych Ocen**: Dla każdego pytania obliczana jest wartość \(x_i \times w_i\). Suma tych wartości jest przechowywana w zmiennej `sum_weighted_avg`.
2. **Sumowanie Wag**: Liczba ankiet \(w_i\) dla każdego pytania jest sumowana w zmiennej `sum_weights`.
3. **Obliczenie Średniej Ważonej**: Średnia ważona jest obliczana jako stosunek `sum_weighted_avg` do `sum_weights`. Wynik jest zaokrąglany do dwóch miejsc po przecinku.

\[
\bar{x}_w = \frac{\text{sum\_weighted\_avg}}{\text{sum\_weights}}
\]

Jeśli `sum_weights` wynosi 0 (np. brak danych), średnia ważona jest ustawiana na "-".

### Obliczanie Procentu Wypełnionych Ankiet
Procent wypełnionych ankiet jest wskaźnikiem reprezentatywności zebranych danych.

**Wzór Matematyczny**:

\[
\text{Procent Wypełnionych Ankiet} (\%) = \left( \frac{\text{Liczba Ankiet}}{\text{Uprawnieni}} \right) \times 100
\]

Gdzie:
- **Liczba Ankiet**: Całkowita liczba wypełnionych ankiet dla danego nauczyciela i przedmiotu.
- **Uprawnieni**: Liczba osób uprawnionych do wypełnienia ankiety.

**Implementacja**:
- `procent_wypelnionych = (liczba_ankiet / uprawnieni) * 100` dla `uprawnieni > 0`. W przeciwnym razie, procent wypełnionych ankiet jest ustawiany na 0.

### Kryteria Filtracji Danych
System stosuje określone kryteria do filtrowania danych, aby zapewnić wiarygodność analiz:

- **Minimalny Procent Wypełnionych Ankiet**: Kryterium: Procent wypełnionych ankiet musi wynosić co najmniej 25%. Uzasadnienie: Zapewnia to, że wyniki są reprezentatywne i nie są wynikiem niskiej liczby odpowiedzi.
- **Minimalna Liczba Ankiet**: Kryterium: Dla tabeli 3.4, liczba ankiet musi wynosić co najmniej 5. Uzasadnienie: Gwarantuje to, że ocena średnia nie jest wynikiem przypadkowych lub minimalnych danych.
- **Średnia Ocena Poniżej 4.0**: Kryterium: Tylko nauczyciele z średnią ocen poniżej 4.0 są uwzględnieni w tabeli 3.4. Uzasadnienie: Identyfikuje nauczycieli, którzy mogą wymagać dodatkowego wsparcia lub szkoleń.

## Struktura Danych
### Kluczowe Zmienne
- **tytul**: Tytuł naukowy nauczyciela (np. Dr., Prof.). Używany do pełnej identyfikacji nauczyciela.
- **imie**: Imię nauczyciela.
- **nazwisko**: Nazwisko nauczyciela.
- **nazwa_przedmiotu**: Nazwa przedmiotu, którego dotyczy ankieta.
- **opis_zajec**: Forma zajęć (np. wykład, ćwiczenia).
- **kod_przedmiotu**: Kod identyfikujący przedmiot.
- **wartosc**: Wartość przypisana odpowiedzi na pytanie ankietowe (np. ocena w skali 1-5).
- **odp_na_wartosc**: Liczba ankiet odpowiadających danemu `wartosc`.
- **uprawnieni**: Liczba osób uprawnionych do wypełnienia ankiety.
- **ilosc_odpowiedzi**: Całkowita liczba wypełnionych ankiet dla danej formy zajęć.

## Architektura Aplikacji
System opiera się na architekturze klient-serwer, gdzie:

- **Frontend**: Interfejs użytkownika zbudowany przy użyciu HTML, CSS (Bootstrap) i JavaScript, umożliwiający interakcję z systemem poprzez przeglądarkę internetową.
- **Backend**: Aplikacja Flask obsługująca logikę biznesową, przetwarzanie danych i komunikację z bazą danych SQLite.
- **Baza Danych**: SQLite przechowuje wszystkie dane ankietowe oraz informacje o przesłanych plikach.

## Instalacja i Konfiguracja
### Wymagania Systemowe
- Python 3.7+
- Pip (Python Package Installer)
- Biblioteki Python: Flask, Flask-SQLAlchemy, Pandas, Werkzeug

### Krok po Kroku
1. **Klonowanie Repozytorium**:
   ```bash
   git clone https://github.com/twoja-nazwa-repozytorium/survey-analysis-app.git
   cd survey-analysis-app
   ```

2. **Tworzenie Wirtualnego Środowiska**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Na Windows: venv\Scripts\activate
   ```

3. **Instalacja Zależności**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Inicjalizacja Bazy Danych**: Aplikacja automatycznie tworzy tabele w bazie danych SQLite podczas pierwszego uruchomienia.

5. **Uruchomienie Aplikacji**:
   ```bash
   python app.py
   ```
   Aplikacja będzie dostępna pod adresem [http://127.0.0.1:5000/](http://127.0.0.1:5000/).

## Przykładowe Formuły Matematyczne
1. **Średnia Ważona**
   
   \[
   \bar{x}_w = \frac{\sum_{i=1}^n (x_i \times w_i)}{\sum_{i=1}^n w_i}
   \]

   - \(x_i\) – Średnia ocenina dla pytania \(i\).
   - \(w_i\) – Liczba ankiet wypełnionych dla pytania \(i\).

2. **Procent Wypełnionych Ankiet**
   
   \[
   \text{Procent Wypełnionych Ankiet} (\%) = \left( \frac{\text{Liczba Ankiet}}{\text{Uprawnieni}} \right) \times 100
   \]

   - **Liczba Ankiet**: Całkowita liczba wypełnionych ankiet.
   - **Uprawnieni**: Liczba osób uprawnionych do wypełnienia ankiety.

## Zakończenie
System Analizy Wyników Ankiet stanowi potężne narzędzie do oceny efektywności dydaktycznej nauczycieli oraz jakości prowadzonych przez nich zajęć. Dzięki zastosowaniu średnich ważonych i odpowiednim kryteriom filtracji, system zapewnia wiarygodne i reprezentatywne wyniki, które mogą pomóc w podejmowaniu decyzji dotyczących dalszego rozwoju kadry dydaktycznej.

System jest skalowalny i elastyczny, co umożliwia jego dostosowanie do potrzeb różnych instytucji edukacyjnych. Dalszy rozwój może obejmować wprowadzenie bardziej zaawansowanych analiz, integrację z innymi systemami oraz zwiększenie interaktywności interfejsu użytkownika.

W razie pytań lub sugestii dotyczących rozwoju systemu, prosimy o kontakt z zespołem.

