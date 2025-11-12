import sqlite3
import texttable as TT

DB = "IoT.db"

# ------------------ Petites utilitaires (simples) ------------------

def draw_query(cur, sql, params=()):
    """Exécute un SELECT et affiche le résultat avec texttable."""
    res = cur.execute(sql, params)
    tbl = TT.Texttable()
    headers = [d[0] for d in res.description]
    tbl.add_rows([headers])
    for row in res:
        tbl.add_row(row)
    tbl.set_header_align(["c"] * len(headers))
    tbl.set_cols_align(["c"] * len(headers))
    print(tbl.draw())

def input_int(msg):
    while True:
        s = input(msg).strip()
        try:
            return int(s)
        except ValueError:
            print("=> Entrez un entier.")

def input_txt(msg, default=None):
    s = input(msg).rstrip()
    if s == "" and default is not None:
        return default
    return s

def table_exists(cur, name):
    return cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,)
    ).fetchone() is not None

def list_and_choose(cur, sql_list, prompt="ID"):
    """Affiche (ID, Label) et renvoie l'ID choisi, ou None si vide."""
    rows = cur.execute(sql_list).fetchall()
    if not rows:
        print("(Aucune donnée)")
        return None
    t = TT.Texttable()
    t.add_rows([["ID", "Label"]] + [list(r) for r in rows])
    t.set_header_align(["c", "c"]); t.set_cols_align(["c", "c"])
    print(t.draw())
    ids = {r[0] for r in rows}
    while True:
        rid = input_int(f"Saisir {prompt} : ")
        if rid in ids:
            return rid
        print("=> ID invalide.")

# ------------------ Affichages ------------------

def show_batiments(cur):
    draw_query(cur, 'SELECT NOM_BATIMENT AS "Bâtiment" FROM BATIMENT ORDER BY NOM_BATIMENT')

def show_salles(cur):
    draw_query(cur, """
        SELECT S.NOM_SALLE AS 'Salle', B.NOM_BATIMENT AS 'Bâtiment'
        FROM SALLE S
        JOIN BATIMENT B ON B.NUM_BATIMENT = S.NUM_BATIMENT
        ORDER BY B.NOM_BATIMENT, S.NOM_SALLE
    """)

def show_capteurs(cur):
    draw_query(cur, """
        SELECT C.NOM_CAPTEUR AS 'Capteur',
               T.NOM_TYPE    AS 'Type',
               T.UNITE       AS 'Unité',
               S.NOM_SALLE   AS 'Salle',
               B.NOM_BATIMENT AS 'Bâtiment',
               R.TYPE_RESEAU AS 'Réseau',
               G.NOM_GATEWAY AS 'Gateway',
               SV.ADRESSE_IP AS 'Serveur'
        FROM CAPTEUR C
        JOIN TYPE T     ON T.NUM_TYPE = C.NUM_TYPE
        JOIN SALLE S    ON S.NUM_SALLE = C.NUM_SALLE
        JOIN BATIMENT B ON B.NUM_BATIMENT = S.NUM_BATIMENT
        JOIN RESEAU R   ON R.NUM_RESEAU = C.NUM_RESEAU
        LEFT JOIN GATEWAY G ON G.NUM_GATEWAY = C.NUM_GATEWAY
        LEFT JOIN SERVEUR SV ON SV.NUM_SERVEUR = G.NUM_SERVEUR
        ORDER BY B.NOM_BATIMENT, S.NOM_SALLE, C.NOM_CAPTEUR
    """)

def show_gateways(cur):
    draw_query(cur, """
        SELECT G.NOM_GATEWAY AS 'Gateway',
               S.NOM_SALLE AS 'Salle',
               B.NOM_BATIMENT AS 'Bâtiment',
               SV.ADRESSE_IP AS 'Serveur'
        FROM GATEWAY G
        JOIN SALLE S    ON S.NUM_SALLE = G.NUM_SALLE
        JOIN BATIMENT B ON B.NUM_BATIMENT = S.NUM_BATIMENT
        LEFT JOIN SERVEUR SV ON SV.NUM_SERVEUR = G.NUM_SERVEUR
        ORDER BY B.NOM_BATIMENT, S.NOM_SALLE, G.NOM_GATEWAY
    """)

def show_topologie(cur):
    print("\n== Topologie : Serveur → Gateway → Capteur ==")
    rows = cur.execute("""
        SELECT SV.ADRESSE_IP, G.NOM_GATEWAY, C.NOM_CAPTEUR, COALESCE(R.TYPE_RESEAU,'?')
        FROM SERVEUR SV
        LEFT JOIN GATEWAY G  ON G.NUM_SERVEUR = SV.NUM_SERVEUR
        LEFT JOIN CAPTEUR C  ON C.NUM_GATEWAY = G.NUM_GATEWAY
        LEFT JOIN RESEAU R   ON R.NUM_RESEAU = C.NUM_RESEAU
        ORDER BY SV.ADRESSE_IP, G.NOM_GATEWAY, C.NOM_CAPTEUR
    """).fetchall()
    current_ip, current_gw = None, None
    printed_gw = False
    for ip, gw, cap, reseau in rows:
        if ip != current_ip:
            if current_ip is not None and not printed_gw:
                print("  (aucune gateway)")
            print(f"Serveur : {ip}")
            current_ip, current_gw, printed_gw = ip, None, False
        if gw is None:
            continue
        if gw != current_gw:
            print(f"  Gateway : {gw}")
            current_gw, printed_gw = gw, True
        if cap:
            print(f"    Capteur : {cap} ({reseau})")
    # dernier serveur sans GW
    if rows:
        last_ip = rows[-1][0]
        n_gw = cur.execute("""
            SELECT COUNT(*) FROM GATEWAY G
            JOIN SERVEUR SV ON SV.NUM_SERVEUR = G.NUM_SERVEUR
            WHERE SV.ADRESSE_IP = ?
        """, (last_ip,)).fetchone()[0]
        if n_gw == 0:
            print("  (aucune gateway)")

    if table_exists(cur, "CONNEXION"):
        print("\n== Topologie : Application → Serveur → Capteur / Type ==")
        rows2 = cur.execute("""
            SELECT A.NOM_APP, SV.ADRESSE_IP, C.NOM_CAPTEUR, T.NOM_TYPE, T.UNITE
            FROM APPLICATION A
            JOIN CONNEXION X ON X.NUM_APP = A.NUM_APP
            JOIN SERVEUR SV  ON SV.NUM_SERVEUR = X.NUM_SERVEUR
            LEFT JOIN GATEWAY G ON G.NUM_SERVEUR = SV.NUM_SERVEUR
            LEFT JOIN CAPTEUR C ON C.NUM_GATEWAY = G.NUM_GATEWAY
            LEFT JOIN TYPE T    ON T.NUM_TYPE = C.NUM_TYPE
            ORDER BY A.NOM_APP, SV.ADRESSE_IP, C.NOM_CAPTEUR
        """).fetchall()
        if not rows2:
            print("(Aucune application liée.)")
        app_now, srv_now = None, None
        for app, ip, cap, tname, unit in rows2:
            if app != app_now:
                print(f"Application : {app}"); app_now, srv_now = app, None
            if ip and ip != srv_now:
                print(f"  Serveur : {ip}"); srv_now = ip
            if cap:
                print(f"    Capteur : {cap} / {tname} ({unit})")
   

# ------------------ INSERT ------------------

def insert_batiment(cur, db):
    nom = input_txt("Nom du bâtiment : ")
    # ID auto simple = max + 1
    next_id = cur.execute('SELECT COALESCE(MAX(NUM_BATIMENT),0)+1 FROM BATIMENT').fetchone()[0]
    cur.execute('INSERT INTO BATIMENT(NUM_BATIMENT, NOM_BATIMENT) VALUES (?,?)', (next_id, nom))
    db.commit(); print("OK.")

def insert_salle(cur, db):
    nom = input_txt("Nom de la salle : ")
    num_b = list_and_choose(cur, 'SELECT NUM_BATIMENT, NOM_BATIMENT FROM BATIMENT ORDER BY NOM_BATIMENT', "NUM_BATIMENT")
    if num_b is None: return
    next_id = cur.execute('SELECT COALESCE(MAX(NUM_SALLE),0)+1 FROM SALLE').fetchone()[0]
    cur.execute('INSERT INTO SALLE(NUM_SALLE, NUM_BATIMENT, NOM_SALLE) VALUES (?,?,?)', (next_id, num_b, nom))
    db.commit(); print("OK.")

def insert_type(cur, db):
    nom = input_txt("Nom du type : ")
    unite = input_txt("Unité : ")
    next_id = cur.execute('SELECT COALESCE(MAX(NUM_TYPE),0)+1 FROM TYPE').fetchone()[0]
    cur.execute('INSERT INTO TYPE(NUM_TYPE, NOM_TYPE, UNITE) VALUES (?,?,?)', (next_id, nom, unite))
    db.commit(); print("OK.")

def insert_reseau(cur, db):
    techno = input_txt("Type réseau (WiFi/LoRaWAN/Sigfox/NB‑IOT) : ")
    debit = input_int("Débit réseau (entier) : ")
    next_id = cur.execute('SELECT COALESCE(MAX(NUM_RESEAU),0)+1 FROM RESEAU').fetchone()[0]
    cur.execute('INSERT INTO RESEAU(NUM_RESEAU, TYPE_RESEAU, DEBIT_RESEAU) VALUES (?,?,?)', (next_id, techno, debit))
    db.commit(); print("OK.")

def insert_serveur(cur, db):
    ip = input_txt("Adresse IP : ")
    next_id = cur.execute('SELECT COALESCE(MAX(NUM_SERVEUR),0)+1 FROM SERVEUR').fetchone()[0]
    cur.execute('INSERT INTO SERVEUR(NUM_SERVEUR, ADRESSE_IP) VALUES (?,?)', (next_id, ip))
    db.commit(); print("OK.")

def insert_gateway(cur, db):
    nom = input_txt("Nom gateway : ")
    num_salle = list_and_choose(cur, 'SELECT NUM_SALLE, NOM_SALLE FROM SALLE ORDER BY NOM_SALLE', "NUM_SALLE")
    if num_salle is None: return
    num_serv = list_and_choose(cur, 'SELECT NUM_SERVEUR, ADRESSE_IP FROM SERVEUR ORDER BY ADRESSE_IP', "NUM_SERVEUR")
    if num_serv is None: return
    next_id = cur.execute('SELECT COALESCE(MAX(NUM_GATEWAY),0)+1 FROM GATEWAY').fetchone()[0]
    cur.execute('INSERT INTO GATEWAY(NUM_GATEWAY, NUM_SERVEUR, NUM_SALLE, NOM_GATEWAY) VALUES (?,?,?,?)',
                (next_id, num_serv, num_salle, nom))
    db.commit(); print("OK.")

def insert_capteur(cur, db):
    nom = input_txt("Nom capteur : ")
    num_salle = list_and_choose(cur, 'SELECT NUM_SALLE, NOM_SALLE FROM SALLE ORDER BY NOM_SALLE', "NUM_SALLE")
    if num_salle is None: return
    num_gw = list_and_choose(cur, 'SELECT NUM_GATEWAY, NOM_GATEWAY FROM GATEWAY ORDER BY NOM_GATEWAY', "NUM_GATEWAY")
    if num_gw is None: return
    num_type = list_and_choose(cur, 'SELECT NUM_TYPE, NOM_TYPE || " (" || UNITE || ")" FROM TYPE ORDER BY NOM_TYPE', "NUM_TYPE")
    if num_type is None: return
    num_res = list_and_choose(cur, 'SELECT NUM_RESEAU, TYPE_RESEAU FROM RESEAU ORDER BY TYPE_RESEAU', "NUM_RESEAU")
    if num_res is None: return
    next_id = cur.execute('SELECT COALESCE(MAX(NUM_CAPTEUR),0)+1 FROM CAPTEUR').fetchone()[0]
    cur.execute("""
        INSERT INTO CAPTEUR(NUM_CAPTEUR, NUM_SALLE, NUM_GATEWAY, NUM_TYPE, NUM_RESEAU, NOM_CAPTEUR)
        VALUES (?,?,?,?,?,?)
    """, (next_id, num_salle, num_gw, num_type, num_res, nom))
    db.commit(); print("OK.")

def insert_application(cur, db):
    nom = input_txt("Nom application : ")
    next_id = cur.execute('SELECT COALESCE(MAX(NUM_APP),0)+1 FROM APPLICATION').fetchone()[0]
    cur.execute('INSERT INTO APPLICATION(NUM_APP, NOM_APP) VALUES (?,?)', (next_id, nom))
    db.commit(); print("OK.")

def insert_connexion(cur, db):
    if not table_exists(cur, "CONNEXION"):
        print("(Créez la table CONNEXION si nécessaire.)")
        return
    num_app = list_and_choose(cur, 'SELECT NUM_APP, NOM_APP FROM APPLICATION ORDER BY NOM_APP', "NUM_APP")
    if num_app is None: return
    num_srv = list_and_choose(cur, 'SELECT NUM_SERVEUR, ADRESSE_IP FROM SERVEUR ORDER BY ADRESSE_IP', "NUM_SERVEUR")
    if num_srv is None: return
    cur.execute('INSERT INTO CONNEXION(NUM_APP, NUM_SERVEUR) VALUES (?,?)', (num_app, num_srv))
    db.commit(); print("OK.")

# ------------------ UPDATE (très simple) ------------------

def update_batiment(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_BATIMENT, NOM_BATIMENT FROM BATIMENT ORDER BY NOM_BATIMENT', "NUM_BATIMENT")
    if nid is None: return
    new_name = input_txt("Nouveau nom (laisser vide pour conserver) : ",
                         default=cur.execute('SELECT NOM_BATIMENT FROM BATIMENT WHERE NUM_BATIMENT=?',(nid,)).fetchone()[0])
    cur.execute('UPDATE BATIMENT SET NOM_BATIMENT=? WHERE NUM_BATIMENT=?', (new_name, nid))
    db.commit(); print("OK.")

def update_salle(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_SALLE, NOM_SALLE FROM SALLE ORDER BY NOM_SALLE', "NUM_SALLE")
    if nid is None: return
    name_def = cur.execute('SELECT NOM_SALLE FROM SALLE WHERE NUM_SALLE=?',(nid,)).fetchone()[0]
    new_name = input_txt("Nouveau nom (vide = garder) : ", default=name_def)
    # possibilité de changer le bâtiment
    if input_txt("Changer de bâtiment ? (o/N) : ").lower() == "o":
        nb = list_and_choose(cur, 'SELECT NUM_BATIMENT, NOM_BATIMENT FROM BATIMENT ORDER BY NOM_BATIMENT', "NUM_BATIMENT")
        if nb is None: return
        cur.execute('UPDATE SALLE SET NOM_SALLE=?, NUM_BATIMENT=? WHERE NUM_SALLE=?', (new_name, nb, nid))
    else:
        cur.execute('UPDATE SALLE SET NOM_SALLE=? WHERE NUM_SALLE=?', (new_name, nid))
    db.commit(); print("OK.")

def update_capteur(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_CAPTEUR, NOM_CAPTEUR FROM CAPTEUR ORDER BY NOM_CAPTEUR', "NUM_CAPTEUR")
    if nid is None: return
    name_def = cur.execute('SELECT NOM_CAPTEUR FROM CAPTEUR WHERE NUM_CAPTEUR=?',(nid,)).fetchone()[0]
    new_name = input_txt("Nouveau nom (vide = garder) : ", default=name_def)
    # changer liaisons ?
    if input_txt("Changer salle/gateway/type/réseau ? (o/N) : ").lower() == "o":
        sid = list_and_choose(cur, 'SELECT NUM_SALLE, NOM_SALLE FROM SALLE ORDER BY NOM_SALLE', "NUM_SALLE")
        if sid is None: return
        gid = list_and_choose(cur, 'SELECT NUM_GATEWAY, NOM_GATEWAY FROM GATEWAY ORDER BY NOM_GATEWAY', "NUM_GATEWAY")
        if gid is None: return
        tid = list_and_choose(cur, 'SELECT NUM_TYPE, NOM_TYPE || " (" || UNITE || ")" FROM TYPE ORDER BY NOM_TYPE', "NUM_TYPE")
        if tid is None: return
        rid = list_and_choose(cur, 'SELECT NUM_RESEAU, TYPE_RESEAU FROM RESEAU ORDER BY TYPE_RESEAU', "NUM_RESEAU")
        if rid is None: return
        cur.execute("""
            UPDATE CAPTEUR
            SET NOM_CAPTEUR=?, NUM_SALLE=?, NUM_GATEWAY=?, NUM_TYPE=?, NUM_RESEAU=?
            WHERE NUM_CAPTEUR=?
        """, (new_name, sid, gid, tid, rid, nid))
    else:
        cur.execute('UPDATE CAPTEUR SET NOM_CAPTEUR=? WHERE NUM_CAPTEUR=?', (new_name, nid))
    db.commit(); print("OK.")

def update_gateway(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_GATEWAY, NOM_GATEWAY FROM GATEWAY ORDER BY NOM_GATEWAY', "NUM_GATEWAY")
    if nid is None: return
    name_def = cur.execute('SELECT NOM_GATEWAY FROM GATEWAY WHERE NUM_GATEWAY=?',(nid,)).fetchone()[0]
    new_name = input_txt("Nouveau nom (vide = garder) : ", default=name_def)
    if input_txt("Changer salle/serveur ? (o/N) : ").lower() == "o":
        sid = list_and_choose(cur, 'SELECT NUM_SALLE, NOM_SALLE FROM SALLE ORDER BY NOM_SALLE', "NUM_SALLE")
        if sid is None: return
        sv = list_and_choose(cur, 'SELECT NUM_SERVEUR, ADRESSE_IP FROM SERVEUR ORDER BY ADRESSE_IP', "NUM_SERVEUR")
        if sv is None: return
        cur.execute('UPDATE GATEWAY SET NOM_GATEWAY=?, NUM_SALLE=?, NUM_SERVEUR=? WHERE NUM_GATEWAY=?',
                    (new_name, sid, sv, nid))
    else:
        cur.execute('UPDATE GATEWAY SET NOM_GATEWAY=? WHERE NUM_GATEWAY=?', (new_name, nid))
    db.commit(); print("OK.")

def update_serveur(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_SERVEUR, ADRESSE_IP FROM SERVEUR ORDER BY ADRESSE_IP', "NUM_SERVEUR")
    if nid is None: return
    ip_def = cur.execute('SELECT ADRESSE_IP FROM SERVEUR WHERE NUM_SERVEUR=?',(nid,)).fetchone()[0]
    new_ip = input_txt("Nouvelle IP (vide = garder) : ", default=ip_def)
    cur.execute('UPDATE SERVEUR SET ADRESSE_IP=? WHERE NUM_SERVEUR=?', (new_ip, nid))
    db.commit(); print("OK.")

def update_type(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_TYPE, NOM_TYPE || " (" || UNITE || ")" FROM TYPE ORDER BY NOM_TYPE', "NUM_TYPE")
    if nid is None: return
    nom_def, uni_def = cur.execute('SELECT NOM_TYPE, UNITE FROM TYPE WHERE NUM_TYPE=?',(nid,)).fetchone()
    new_nom = input_txt("Nouveau nom (vide = garder) : ", default=nom_def)
    new_uni = input_txt("Nouvelle unité (vide = garder) : ", default=uni_def)
    cur.execute('UPDATE TYPE SET NOM_TYPE=?, UNITE=? WHERE NUM_TYPE=?', (new_nom, new_uni, nid))
    db.commit(); print("OK.")

def update_reseau(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_RESEAU, TYPE_RESEAU FROM RESEAU ORDER BY TYPE_RESEAU', "NUM_RESEAU")
    if nid is None: return
    name_def, debit_def = cur.execute('SELECT TYPE_RESEAU, DEBIT_RESEAU FROM RESEAU WHERE NUM_RESEAU=?',(nid,)).fetchone()
    new_name = input_txt("Nouveau type (vide = garder) : ", default=name_def)
    s = input_txt(f"Nouveau débit (vide = garder {debit_def}) : ", default=str(debit_def))
    new_debit = int(s) if s.strip() != "" else debit_def
    cur.execute('UPDATE RESEAU SET TYPE_RESEAU=?, DEBIT_RESEAU=? WHERE NUM_RESEAU=?', (new_name, new_debit, nid))
    db.commit(); print("OK.")

def update_application(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_APP, NOM_APP FROM APPLICATION ORDER BY NOM_APP', "NUM_APP")
    if nid is None: return
    app_def = cur.execute('SELECT NOM_APP FROM APPLICATION WHERE NUM_APP=?',(nid,)).fetchone()[0]
    new_name = input_txt("Nouveau nom (vide = garder) : ", default=app_def)
    cur.execute('UPDATE APPLICATION SET NOM_APP=? WHERE NUM_APP=?', (new_name, nid))
    db.commit(); print("OK.")

# ------------------ DELETE (simple, avec petites cascades) ------------------

def del_capteur(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_CAPTEUR, NOM_CAPTEUR FROM CAPTEUR ORDER BY NOM_CAPTEUR', "NUM_CAPTEUR")
    if nid is None: return
    cur.execute('DELETE FROM CAPTEUR WHERE NUM_CAPTEUR=?', (nid,)); db.commit(); print("OK.")

def del_gateway(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_GATEWAY, NOM_GATEWAY FROM GATEWAY ORDER BY NOM_GATEWAY', "NUM_GATEWAY")
    if nid is None: return
    cur.execute('DELETE FROM CAPTEUR WHERE NUM_GATEWAY=?', (nid,))
    cur.execute('DELETE FROM GATEWAY WHERE NUM_GATEWAY=?', (nid,))
    db.commit(); print("OK. (capteurs liés supprimés)")

def del_salle(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_SALLE, NOM_SALLE FROM SALLE ORDER BY NOM_SALLE', "NUM_SALLE")
    if nid is None: return
    # supprime capteurs + gateways de la salle
    for (gid,) in cur.execute('SELECT NUM_GATEWAY FROM GATEWAY WHERE NUM_SALLE=?', (nid,)).fetchall():
        cur.execute('DELETE FROM CAPTEUR WHERE NUM_GATEWAY=?', (gid,))
        cur.execute('DELETE FROM GATEWAY WHERE NUM_GATEWAY=?', (gid,))
    cur.execute('DELETE FROM CAPTEUR WHERE NUM_SALLE=?', (nid,))
    cur.execute('DELETE FROM SALLE WHERE NUM_SALLE=?', (nid,))
    db.commit(); print("OK.")

def del_batiment(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_BATIMENT, NOM_BATIMENT FROM BATIMENT ORDER BY NOM_BATIMENT', "NUM_BATIMENT")
    if nid is None: return
    # supprimer toutes les salles (et dépendances)
    salles = cur.execute('SELECT NUM_SALLE FROM SALLE WHERE NUM_BATIMENT=?', (nid,)).fetchall()
    for (sid,) in salles:
        for (gid,) in cur.execute('SELECT NUM_GATEWAY FROM GATEWAY WHERE NUM_SALLE=?', (sid,)).fetchall():
            cur.execute('DELETE FROM CAPTEUR WHERE NUM_GATEWAY=?', (gid,))
            cur.execute('DELETE FROM GATEWAY WHERE NUM_GATEWAY=?', (gid,))
        cur.execute('DELETE FROM CAPTEUR WHERE NUM_SALLE=?', (sid,))
        cur.execute('DELETE FROM SALLE WHERE NUM_SALLE=?', (sid,))
    cur.execute('DELETE FROM BATIMENT WHERE NUM_BATIMENT=?', (nid,))
    db.commit(); print("OK.")

def del_serveur(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_SERVEUR, ADRESSE_IP FROM SERVEUR ORDER BY ADRESSE_IP', "NUM_SERVEUR")
    if nid is None: return
    if table_exists(cur, "CONNEXION"):
        cur.execute('DELETE FROM CONNEXION WHERE NUM_SERVEUR=?', (nid,))
    for (gid,) in cur.execute('SELECT NUM_GATEWAY FROM GATEWAY WHERE NUM_SERVEUR=?', (nid,)).fetchall():
        cur.execute('DELETE FROM CAPTEUR WHERE NUM_GATEWAY=?', (gid,))
    cur.execute('DELETE FROM GATEWAY WHERE NUM_SERVEUR=?', (nid,))
    cur.execute('DELETE FROM SERVEUR WHERE NUM_SERVEUR=?', (nid,))
    db.commit(); print("OK.")

def del_application(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_APP, NOM_APP FROM APPLICATION ORDER BY NOM_APP', "NUM_APP")
    if nid is None: return
    if table_exists(cur, "CONNEXION"):
        cur.execute('DELETE FROM CONNEXION WHERE NUM_APP=?', (nid,))
    cur.execute('DELETE FROM APPLICATION WHERE NUM_APP=?', (nid,))
    db.commit(); print("OK.")

def del_type(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_TYPE, NOM_TYPE || " (" || UNITE || ")" FROM TYPE ORDER BY NOM_TYPE', "NUM_TYPE")
    if nid is None: return
    cur.execute('DELETE FROM CAPTEUR WHERE NUM_TYPE=?', (nid,))
    cur.execute('DELETE FROM TYPE WHERE NUM_TYPE=?', (nid,))
    db.commit(); print("OK. (capteurs liés supprimés)")

def del_reseau(cur, db):
    nid = list_and_choose(cur, 'SELECT NUM_RESEAU, TYPE_RESEAU FROM RESEAU ORDER BY TYPE_RESEAU', "NUM_RESEAU")
    if nid is None: return
    cur.execute('DELETE FROM CAPTEUR WHERE NUM_RESEAU=?', (nid,))
    cur.execute('DELETE FROM RESEAU WHERE NUM_RESEAU=?', (nid,))
    db.commit(); print("OK. (capteurs liés supprimés)")

# ------------------ Menus ------------------

def menu_afficher(cur):
    while True:
        print(f"""
Base : {DB}
  /Affichage :
    1 - Bâtiments
    2 - Salles
    3 - Capteurs
    4 - Gateways
    5 - Topologie
    9 - SQL libre
    0 - Retour
""")
        c = input_txt("Choix : ")
        if c == "1": show_batiments(cur)
        elif c == "2": show_salles(cur)
        elif c == "3": show_capteurs(cur)
        elif c == "4": show_gateways(cur)
        elif c == "5": show_topologie(cur)
        elif c == "9":
            sql = input_txt("SQL> ")
            try:
                draw_query(cur, sql)
            except Exception as e:
                print("Erreur SQL :", e)
        elif c == "0": return
        else: print("Choix invalide.")

def menu_inserer(cur, db):
    while True:
        print(f"""
Base : {DB}
  /Insertion :
    1 - Bâtiment
    2 - Salle
    3 - Capteur
    4 - Gateway
    5 - Serveur
    6 - Application
    7 - Type
    8 - Réseau
    9 - Connexion (App <-> Serv)
    0 - Retour
""")
        c = input_txt("Choix : ")
        if   c == "1": insert_batiment(cur, db)
        elif c == "2": insert_salle(cur, db)
        elif c == "3": insert_capteur(cur, db)
        elif c == "4": insert_gateway(cur, db)
        elif c == "5": insert_serveur(cur, db)
        elif c == "6": insert_application(cur, db)
        elif c == "7": insert_type(cur, db)
        elif c == "8": insert_reseau(cur, db)
        elif c == "9": insert_connexion(cur, db)
        elif c == "0": return
        else: print("Choix invalide.")

def menu_modifier(cur, db):
    while True:
        print(f"""
Base : {DB}
  /Modification :
    1 - Bâtiment
    2 - Salle
    3 - Capteur
    4 - Gateway
    5 - Serveur
    6 - Application
    7 - Type
    8 - Réseau
    0 - Retour
""")
        c = input_txt("Choix : ")
        if   c == "1": update_batiment(cur, db)
        elif c == "2": update_salle(cur, db)
        elif c == "3": update_capteur(cur, db)
        elif c == "4": update_gateway(cur, db)
        elif c == "5": update_serveur(cur, db)
        elif c == "6": update_application(cur, db)
        elif c == "7": update_type(cur, db)
        elif c == "8": update_reseau(cur, db)
        elif c == "0": return
        else: print("Choix invalide.")

def menu_supprimer(cur, db):
    while True:
        print(f"""
Base : {DB}
  /Suppression :
    1 - Bâtiment
    2 - Salle
    3 - Capteur
    4 - Gateway
    5 - Serveur
    6 - Application
    7 - Type
    8 - Réseau
    0 - Retour
""")
        c = input_txt("Choix : ")
        if   c == "1": del_batiment(cur, db)
        elif c == "2": del_salle(cur, db)
        elif c == "3": del_capteur(cur, db)
        elif c == "4": del_gateway(cur, db)
        elif c == "5": del_serveur(cur, db)
        elif c == "6": del_application(cur, db)
        elif c == "7": del_type(cur, db)
        elif c == "8": del_reseau(cur, db)
        elif c == "0": return
        else: print("Choix invalide.")

# ------------------ Main ------------------

def main():
    print("TP2")
    with sqlite3.connect(DB) as db:
        cur = db.cursor()
        while True:
            print(f"""
Base : {DB}
  1 - Afficher
  2 - Insérer
  3 - Modifier
  4 - Supprimer
  0 - Quitter
""")
            ch = input_txt("Choix : ")
            if   ch == "1": menu_afficher(cur)
            elif ch == "2": menu_inserer(cur, db)
            elif ch == "3": menu_modifier(cur, db)
            elif ch == "4": menu_supprimer(cur, db)
            elif ch == "0":
                print("Au revoir."); break
            else:
                print("Choix invalide.")

if __name__ == "__main__":
    main()