import os
import hashlib
import pandas as pd
from flask import Flask, request, redirect, url_for, render_template, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from sqlalchemy import func, distinct, and_, cast, String, Integer, Float, text
import logging
from collections import defaultdict

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max file size: 16 MB

db = SQLAlchemy(app)
ALLOWED_EXTENSIONS = {'csv'}

# Configuration for excluded questions and units
EXCLUDED_QUESTIONS = [
    "Czy stopień trudności ocenianych ćwiczeń, w porównaniu z innymi, był duży?",
    "Oceń własną frekwencję na wykładach"
]

INITIAL_QUESTIONS = [
    "Czy na początku ćwiczeń ich cel i zakres zostały jasno określone?",
    "Czy na początku wykładów cel i zakres przedmiotu został jasno określony?"
]

EXCLUDED_UNIT = "Wydział Nauk Społecznych"

# Database models
class UploadedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_hash = db.Column(db.String(32), unique=True)  # MD5 hash of the file
    filename = db.Column(db.String(200), unique=True)

class Data(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cykl_dydaktyczny = db.Column(db.String(100), name='cykl dydaktyczny')
    kod_przedmiotu = db.Column(db.String(100), name='kod przedmiotu')
    nazwa_przedmiotu = db.Column(db.String(200), name='nazwa przedmiotu')
    jezyk_prowadzenia_przedmiotu = db.Column(db.String(50), name='język prowadzenia przedmiotu')
    id_zajec = db.Column(db.Integer, name='id zajęć')
    kod_zajec = db.Column(db.String(50), name='kod zajęć')
    opis_zajec = db.Column(db.String(200), name='opis zajęć')
    nr_grupy = db.Column(db.Integer, name='nr grupy')
    id_osoby = db.Column(db.Integer, name='id osoby')
    tytul = db.Column(db.String(50), name='tytul')
    imie = db.Column(db.String(100), name='imie')
    nazwisko = db.Column(db.String(100), name='nazwisko')
    kod_jednostki = db.Column(db.String(100), name='kod jednostki')
    jednostka = db.Column(db.String(200), name='jednostka')
    id_pytania = db.Column(db.Integer, name='id pytania')
    kolejnosc = db.Column(db.Integer, name='kolejność')
    tresc_pytania = db.Column(db.String(500), name='treść pytania')
    wartosc = db.Column(db.String(50), name='wartość')
    opis_odpowiedzi_pl = db.Column(db.String(200), name='opis odpowiedzi (PL)')
    opis_odpowiedzi_en = db.Column(db.String(200), name='opis odpowiedzi (EN)')
    odp_na_wartosc = db.Column(db.String(50), name='odp_na_wartosc')
    odp_na_pytanie = db.Column(db.String(50), name='odp_na_pytanie')
    udzial_wart_w_pytaniu = db.Column(db.String(50), name='udzial_wart_w_pytaniu')
    uprawnieni = db.Column(db.Integer, name='uprawnieni')
    udzial_wartosci_w_uprawnionych = db.Column(db.String(50), name='udzial_wartosci_w_uprawnionych')

with app.app_context():
    db.create_all()

def allowed_file(filename):
    print(f"[DEBUG] Sprawdzanie pliku: {filename}")
    result = '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    print(f"[DEBUG] Czy plik jest dozwolony? {result}")
    return result

def calculate_file_hash(file_path):
    print(f"[DEBUG] Obliczanie hash MD5 dla pliku: {file_path}")
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    file_hash = hasher.hexdigest()
    print(f"[DEBUG] Obliczony hash MD5: {file_hash}")
    return file_hash

def parse_teacher_name(nauczyciel):
    parts = nauczyciel.strip().split()
    if len(parts) >= 2:
        imie = parts[0]
        nazwisko = ' '.join(parts[1:])
    else:
        imie = parts[0]
        nazwisko = ''
    return nazwisko, imie

def calculate_weighted_average(data_rows):
    total_weighted_score = 0
    total_responses = 0

    for row in data_rows:
        try:
            wartosc = float(row.wartosc.replace(',', '.'))
            odp_na_wartosc = int(float(row.odp_na_wartosc.replace(',', '.')))
            total_weighted_score += wartosc * odp_na_wartosc
            total_responses += odp_na_wartosc
        except (ValueError, TypeError) as e:
            print(f"[ERROR] Błąd podczas przetwarzania wiersza: {e}")
            continue  # Skip invalid data

    average = (total_weighted_score / total_responses) if total_responses > 0 else None
    return average, total_responses

def class_details(id_zajec, id_osoby=None):
    query = db.session.query(
        Data.uprawnieni.label('uprawnieni_first'),
        func.sum(cast(Data.odp_na_wartosc, Integer)).label('ilosc_odpowiedzi')
    ).filter(
        Data.id_zajec == id_zajec
    )
    
    if id_osoby is not None:
        query = query.filter(Data.id_osoby == id_osoby)
    
    query = query.filter(
        Data.tresc_pytania.ilike("Czy na początku%")
    )
    
    record = query.first()

    if record:
        return {
            "id_zajec": id_zajec,
            "uprawnieni": record.uprawnieni_first if record.uprawnieni_first is not None else 0,
            "ilosc_odpowiedzi": record.ilosc_odpowiedzi if record.ilosc_odpowiedzi is not None else 0
        }
    else:
        return {
            "error": "Nie znaleziono danych dla podanego ID zajęć" + (f" i osoby {id_osoby}" if id_osoby else "")
        }
        
def calculate_average_rating(nauczyciel, exclude_unit=True):
    nazwisko, imie = parse_teacher_name(nauczyciel)
    query = db.session.query(
        Data.wartosc,
        Data.odp_na_wartosc
    ).filter(
        Data.nazwisko == nazwisko,
        Data.imie == imie,
        Data.tresc_pytania.notin_(EXCLUDED_QUESTIONS)
    )
    
    if exclude_unit:
        query = query.filter(Data.jednostka != EXCLUDED_UNIT)
    
    data_rows = query.all()

    average_grade, total_responses = calculate_weighted_average(data_rows)

    return round(average_grade, 2) if average_grade is not None else None

def calculate_average_for_class(id_zajec):
    data_rows = db.session.query(
        Data.wartosc,
        Data.odp_na_wartosc
    ).filter(
        Data.id_zajec == id_zajec,
        Data.tresc_pytania.notin_(EXCLUDED_QUESTIONS)
    ).all()

    average_grade, total_responses = calculate_weighted_average(data_rows)

    class_data = class_details(id_zajec)
    liczba_ankiet = class_data.get('ilosc_odpowiedzi', 0)

    return round(average_grade, 2) if average_grade is not None else None, liczba_ankiet

def get_filtered_teacher_data():
    print("[DEBUG] Pobieranie danych dla tabeli 3.4")
    classes = db.session.query(
        Data.nazwisko,
        Data.imie,
        Data.tytul,  # Dodanie pola 'tytul'
        Data.nazwa_przedmiotu,
        Data.opis_zajec,
        Data.jednostka,
        Data.id_zajec,
        Data.kod_przedmiotu
    ).group_by(
        Data.nazwisko,
        Data.imie,
        Data.tytul,  # Dodanie pola 'tytul' do grupowania
        Data.nazwa_przedmiotu,
        Data.opis_zajec,
        Data.kod_przedmiotu,
        Data.id_zajec
    ).all()

    filtered_data = []
    for c in classes:
        id_zajec = c.id_zajec
        srednia_ocena, liczba_ankiet = calculate_average_for_class(id_zajec)

        print(f"[DEBUG] Sprawdzanie nauczyciela: {c.imie} {c.nazwisko},przedmiot: {c.nazwa_przedmiotu} , średnia: {srednia_ocena}, liczba ankiet: {liczba_ankiet}")
        if srednia_ocena is not None and srednia_ocena < 4.0 and liczba_ankiet >= 5:
            nauczyciel_pewny = f"{c.tytul} {c.imie} {c.nazwisko}" if c.tytul else f"{c.imie} {c.nazwisko}"
            filtered_data.append({
                "nauczyciel": nauczyciel_pewny,
                "nazwa_przedmiotu": c.nazwa_przedmiotu,
                "forma_zajec": c.opis_zajec,
                "kod_przedmiotu": c.kod_przedmiotu,
                "srednia_ocena": srednia_ocena,
                "liczba_ankiet": liczba_ankiet
            })

    print(f"[DEBUG] Filtracja zakończona, liczba nauczycieli: {len(filtered_data)}")
    return filtered_data

def calculate_average_rating_for_class(nazwa_przedmiotu):
    data_rows = db.session.query(
        Data.wartosc,
        Data.odp_na_wartosc
    ).filter(
        Data.nazwa_przedmiotu == nazwa_przedmiotu,
        Data.tresc_pytania.notin_(EXCLUDED_QUESTIONS)
    ).all()

    average_grade, total_responses = calculate_weighted_average(data_rows)

    return round(average_grade, 2) if average_grade is not None else None

def class_details_by_name(nazwa_przedmiotu):
    record = db.session.query(
        Data.uprawnieni.label('uprawnieni_first'),
        func.sum(cast(Data.odp_na_wartosc, Integer)).label('ilosc_odpowiedzi')
    ).filter(
        Data.nazwa_przedmiotu == nazwa_przedmiotu,
        Data.tresc_pytania.ilike("Czy na początku%")
    ).first()

    if record:
        return {
            "nazwa_przedmiotu": nazwa_przedmiotu,
            "uprawnieni": record.uprawnieni_first if record.uprawnieni_first is not None else 0,
            "ilosc_odpowiedzi": record.ilosc_odpowiedzi if record.ilosc_odpowiedzi is not None else 0
        }
    else:
        return {
            "error": "No data found for the given class name"
        }



@app.route('/clear_data', methods=['POST'])
def clear_data():
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        for filename in os.listdir(upload_folder):
            file_path = os.path.join(upload_folder, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)

        result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        for table in result:
            table_name = table[0]
            if table_name != 'migrations':
                db.session.execute(text(f"DELETE FROM {table_name}"))
        db.session.commit()

        flash("Wszystkie pliki i dane z bazy zostały usunięte.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Błąd podczas usuwania plików i danych: {e}', 'danger')

    return redirect(url_for('upload_file'))



@app.route('/data')
def view_data():
    data_entries = Data.query.all()
    return render_template('data.html', data_entries=data_entries)



@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Brak pliku w żądaniu')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('Nie wybrano pliku')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])

            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            file.save(file_path)

            file_hash = calculate_file_hash(file_path)

            existing_file = UploadedFile.query.filter_by(file_hash=file_hash).first()
            if existing_file:
                os.remove(file_path)
                flash('Ten plik już istnieje w bazie danych.')
                return redirect(request.url)

            new_file = UploadedFile(file_hash=file_hash, filename=filename)
            db.session.add(new_file)
            db.session.commit()

            try:
                df = pd.read_csv(file_path, delimiter=';', encoding='utf-8')
                for _, row in df.iterrows():
                    data_entry = Data(
                        cykl_dydaktyczny=row['cykl dydaktyczny'],
                        kod_przedmiotu=row['kod przedmiotu'],
                        nazwa_przedmiotu=row['nazwa przedmiotu'],
                        jezyk_prowadzenia_przedmiotu=row['język prowadzenia przedmiotu'],
                        id_zajec=row['id zajęć'],
                        kod_zajec=row['kod zajęć'],
                        opis_zajec=row['opis zajęć'],
                        nr_grupy=row['nr grupy'],
                        id_osoby=row['id osoby'],
                        tytul=row['tytul'],
                        imie=row['imie'],
                        nazwisko=row['nazwisko'],
                        kod_jednostki=row['kod jednostki'],
                        jednostka=row['jednostka'],
                        id_pytania=row['id pytania'],
                        kolejnosc=row['kolejność'],
                        tresc_pytania=row['treść pytania'],
                        wartosc=row['wartość'],
                        opis_odpowiedzi_pl=row['opis odpowiedzi (PL)'],
                        opis_odpowiedzi_en=row['opis odpowiedzi (EN)'],
                        odp_na_wartosc=row['odp_na_wartosc'],
                        odp_na_pytanie=row['odp_na_pytanie'],
                        udzial_wart_w_pytaniu=row['udzial_wart_w_pytaniu'],
                        uprawnieni=row['uprawnieni'],
                        udzial_wartosci_w_uprawnionych=row['udzial_wartosci_w_uprawnionych']
                    )
                    db.session.add(data_entry)

                db.session.commit()
                flash('Plik został pomyślnie przesłany i przetworzony')
            except Exception as e:
                db.session.rollback()
                flash(f'Wystąpił błąd podczas przetwarzania pliku: {e}')
            return redirect(url_for('upload_file'))

    return render_template('upload.html')



@app.route('/unique_classes')
def unique_classes_details():
    unit_filter = request.args.get('unit', None)

    # Dodajemy Data.id_osoby do zapytania
    query = db.session.query(
        Data.imie,
        Data.nazwisko,
        Data.id_zajec,
        Data.jednostka,
        Data.id_osoby  # Nowy parametr
    ).group_by(
        Data.nazwisko,
        Data.imie,
        Data.id_zajec,
        Data.jednostka,
        Data.id_osoby  # Grupowanie po id_osoby
    )

    if unit_filter:
        query = query.filter(Data.jednostka == unit_filter)

    records = query.all()

    grouped_data = defaultdict(list)
    for row in records:
        nauczyciel = f"{row.imie} {row.nazwisko}"
        id_zajec = row.id_zajec
        id_osoby = row.id_osoby  # Pobieramy id_osoby

        # Przekazujemy oba parametry do class_details
        data = class_details(id_zajec, id_osoby)
        if 'error' in data:
            # Opcjonalnie: obsłuż błędy, np. pomiń ten rekord
            continue

        liczba_uprawnionych = data.get('uprawnieni', 0)
        liczba_odpowiedzi = data.get('ilosc_odpowiedzi', 0)

        grouped_data[nauczyciel].append({
            'id_zajec': id_zajec,
            'uprawnieni': liczba_uprawnionych,
            'ilosc_odpowiedzi': liczba_odpowiedzi,
            'jednostka': row.jednostka
        })

    tabela_details = [
        {
            'nauczyciel': nauczyciel,
            'zajecia': zajecia
        }
        for nauczyciel, zajecia in grouped_data.items()
    ]

    return render_template('unique_classes.html', tabela_details=tabela_details)



@app.route('/tabela31')
def tabela31():
    teachers = db.session.query(
        Data.nazwisko,
        Data.imie,
        Data.id_zajec
    ).filter(
        Data.jednostka == "Wydział Nauk Społecznych"
    ).group_by(
        Data.nazwisko,
        Data.imie,
        Data.id_zajec
    ).all()

    teacher_data = {}
    for teacher in teachers:
        nauczyciel = f"{teacher.imie} {teacher.nazwisko}"
        if nauczyciel not in teacher_data:
            teacher_data[nauczyciel] = []
        teacher_data[nauczyciel].append(teacher.id_zajec)

    tabela_dane = []
    for nauczyciel, zajecia_ids in teacher_data.items():
        total_uprawnieni = 0
        total_odpowiedzi = 0

        for id_zajec in zajecia_ids:
            data = class_details(id_zajec)

            total_uprawnieni += data.get("uprawnieni", 0)
            total_odpowiedzi += data.get("ilosc_odpowiedzi", 0)

        procent_wypelnionych = (total_odpowiedzi / total_uprawnieni * 100) if total_uprawnieni else 0

        if procent_wypelnionych < 25:
            srednia_ocena = "-"
        else:
            # Przekazujemy exclude_unit=False, aby uwzględnić jednostkę "Wydział Nauk Społecznych"
            srednia_ocena = calculate_average_rating(nauczyciel, exclude_unit=False)

            # Dodatkowo, jeśli nadal zwraca None, ustawiamy "-"
            if srednia_ocena is None:
                srednia_ocena = "-"

        tabela_dane.append({
            "nauczyciel": nauczyciel,
            "liczba_ankiet": total_odpowiedzi,
            "liczba_uprawnionych": total_uprawnieni,
            "procent_wypelnionych": round(procent_wypelnionych, 2),
            "srednia_ocena": srednia_ocena
        })

    return render_template('tabela31.html', tabela_dane=tabela_dane)



@app.route('/tabela32')
def tabela32():
    teachers = db.session.query(
        Data.nazwisko,
        Data.imie
    ).filter(
        Data.jednostka == "Wydział Nauk Społecznych"
    ).group_by(
        Data.nazwisko,
        Data.imie
    ).order_by(
        Data.nazwisko, Data.imie
    ).all()

    tabela_dane = []
    for teacher in teachers:
        nauczyciel = f"{teacher.imie} {teacher.nazwisko}"
        # Przekazujemy exclude_unit=False, aby uwzględnić "Wydział Nauk Społecznych"
        srednia_ocena = calculate_average_rating(nauczyciel, exclude_unit=False)
        tabela_dane.append({
            "nauczyciel": nauczyciel,
            "srednia_ocena": srednia_ocena if srednia_ocena is not None else "-"
        })

    return render_template('tabela32.html', tabela_dane=tabela_dane)


@app.route('/tabela33')
def tabela33():
    teachers = db.session.query(
        Data.nazwisko,
        Data.imie,
        Data.jednostka,
        Data.id_zajec
    ).filter(
        Data.jednostka != "Wydział Nauk Społecznych"
    ).group_by(
        Data.nazwisko,
        Data.imie,
        Data.jednostka,
        Data.id_zajec
    ).order_by(
        Data.jednostka, Data.nazwisko, Data.imie
    ).all()

    tabela_dane = {}
    sum_weighted_avg = 0
    sum_weights = 0

    for teacher in teachers:
        nauczyciel = f"{teacher.imie} {teacher.nazwisko}"
        jednostka = teacher.jednostka
        id_zajec = teacher.id_zajec

        data = class_details(id_zajec)
        if "error" in data:
            continue

        liczba_uprawnionych = data.get("uprawnieni", 0)
        liczba_ankiet = data.get("ilosc_odpowiedzi", 0)

        # Obliczenie procentu wypełnionych ankiet
        procent_wypelnionych = (liczba_ankiet / liczba_uprawnionych * 100) if liczba_uprawnionych else 0

        # Sprawdzenie, czy procent wypełnionych ankiet jest wystarczający (minimum 25%)
        if procent_wypelnionych < 25:
            srednia_ocena = "-"
        else:
            srednia_ocena = calculate_average_rating(nauczyciel)
            # Jeśli calculate_average_rating zwróci None, ustaw "-"
            if srednia_ocena is None:
                srednia_ocena = "-"

        if jednostka not in tabela_dane:
            tabela_dane[jednostka] = []

        tabela_dane[jednostka].append({
            "nauczyciel": nauczyciel,
            "liczba_ankiet": liczba_ankiet,
            "liczba_uprawnionych": liczba_uprawnionych,
            "procent_wypelnionych": round(procent_wypelnionych, 2),
            "srednia_ocena": srednia_ocena
        })

        # Dodawanie do sumy tylko, jeśli procent wypełnionych ankiet jest >= 25% i srednia_ocena nie jest "-"
        if srednia_ocena != "-" and procent_wypelnionych >= 25:
            sum_weighted_avg += srednia_ocena * liczba_ankiet
            sum_weights += liczba_ankiet

    ogolna_srednia_wazona = round(sum_weighted_avg / sum_weights, 2) if sum_weights > 0 else "-"

    return render_template('tabela33.html', tabela_dane=tabela_dane, ogolna_srednia_wazona=ogolna_srednia_wazona)



@app.route('/tabela34')
def tabela34():
    filtered_data = get_filtered_teacher_data()

    return render_template('tabela34.html', tabela_dane=filtered_data)



@app.route('/tabela21')
def tabela21():
    per_class_data = db.session.query(
        Data.nazwa_przedmiotu,
        Data.id_zajec
    ).group_by(
        Data.nazwa_przedmiotu,
        Data.id_zajec
    ).all()

    tabela21 = []
    for row in per_class_data:
        nazwa_przedmiotu = row.nazwa_przedmiotu
        id_zajec = row.id_zajec

        class_data = class_details(id_zajec)
        liczba_uprawnionych = class_data.get('uprawnieni', 0)
        liczba_ankiet = class_data.get('ilosc_odpowiedzi', 0)
        procent_ankiet = (liczba_ankiet / liczba_uprawnionych * 100) if liczba_uprawnionych else 0

        srednia_ocena, _ = calculate_average_for_class(id_zajec)
        srednia_ocena = srednia_ocena if procent_ankiet >= 25 else "-"

        tabela21.append({
            'nazwa_przedmiotu': nazwa_przedmiotu,
            'liczba_ankiet': liczba_ankiet,
            'liczba_uprawnionych': liczba_uprawnionych,
            'procent_ankiet': round(procent_ankiet, 2),
            'srednia_ocena': srednia_ocena
        })

    tabela21 = sorted(tabela21, key=lambda x: x['nazwa_przedmiotu'])

    return render_template('tabela21.html', tabela21=tabela21)



@app.route('/tabela22')
def tabela22():
    subjects = db.session.query(
        Data.nazwa_przedmiotu
    ).group_by(
        Data.nazwa_przedmiotu
    ).all()

    tabela22 = []
    for subject in subjects:
        nazwa_przedmiotu = subject.nazwa_przedmiotu
        srednia_ocena = calculate_average_rating_for_class(nazwa_przedmiotu)
        tabela22.append({
            'nazwa_przedmiotu': nazwa_przedmiotu,
            'srednia_ocena': srednia_ocena if srednia_ocena is not None else "-"
        })

    return render_template('tabela22.html', tabela22=tabela22)



@app.route('/analiza_wynikow')
def analiza_wynikow():
    wyniki = db.session.query(
        Data.nazwisko,
        Data.imie,
        Data.jednostka
    ).group_by(
        Data.nazwisko,
        Data.imie,
        Data.jednostka
    ).all()

    opis = {
        'srednie_2_3': 0,
        'srednie_3_4': 0,
        'srednie_4_5': 0,
        'srednie_5': 0
    }

    for wynik in wyniki:
        nauczyciel = f"{wynik.imie} {wynik.nazwisko}"
        srednia_ocena = calculate_average_rating(nauczyciel)

        if srednia_ocena is None:
            continue

        if 2.0 <= srednia_ocena < 3.0:
            opis['srednie_2_3'] += 1
        elif 3.0 <= srednia_ocena < 4.0:
            opis['srednie_3_4'] += 1
        elif 4.0 <= srednia_ocena < 5.0:
            opis['srednie_4_5'] += 1
        elif srednia_ocena == 5.0:
            opis['srednie_5'] += 1

    total_nauczycieli = sum(opis.values())
    opis_procentowy = {k: (v / total_nauczycieli * 100) if total_nauczycieli else 0 for k, v in opis.items()}

    opis_text = (
        f"Większość nauczycieli z Instytutów Wydziału Nauk Społecznych została oceniona "
        f"{'dobrze' if opis_procentowy['srednie_3_4'] > 50 else 'bardzo dobrze'}, "
        f"tj. {round(opis_procentowy['srednie_2_3'], 2)}% uzyskało ocenę średnią 2,0 - 3,0, "
        f"{round(opis_procentowy['srednie_3_4'], 2)}% ocenę średnią 3,0 - 4,0, "
        f"{round(opis_procentowy['srednie_4_5'], 2)}% ocenę średnią 4,0 - 5,0 oraz "
        f"{round(opis_procentowy['srednie_5'], 2)}% ocenę średnią 5,0."
    )

    return render_template('analiza_wynikow.html', opis=opis_text)



if __name__ == '__main__':
    app.run(debug=True)
