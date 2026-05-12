from flask import Flask, render_template, request, redirect, session
import pandas as pd
import sqlite3
import os
import traceback

app = Flask(__name__)
app.secret_key = "segredo_super_secreto"

DB = "meu_banco.db"

# ---------------------------
# CRIAR BANCO
# ---------------------------
def criar_banco():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS producao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produtor TEXT,
        produto TEXT,
        quantidade REAL,
        preco REAL,
        localidade TEXT,
        data TEXT
    )
    """)

    conn.commit()
    conn.close()

criar_banco()

# ---------------------------
# LOGIN
# ---------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("user")
        senha = request.form.get("senha")

        if user == "admin" and senha == "123":
            session["logado"] = True

            # 🔥 VERIFICA SE JÁ TEM DADOS NO BANCO
            conn = sqlite3.connect(DB)
            cursor = conn.cursor()

            try:
                cursor.execute("SELECT COUNT(*) FROM producao")
                total = cursor.fetchone()[0]
            except:
                total = 0  # caso tabela ainda não exista

            conn.close()

            # 🔥 REDIRECIONAMENTO INTELIGENTE
            if total > 0:
                return redirect("/dashboard")
            else:
                return redirect("/upload")

    return render_template("login.html")
# ---------------------------
# FUNÇÃO INTELIGENTE DE MAPEAMENTO
# ---------------------------
def mapear_colunas(df):
    df.columns = df.columns.str.strip().str.lower()

    mapa = {}

    for col in df.columns:
        if "produtor" in col:
            mapa[col] = "produtor"
        elif "produto" in col:
            mapa[col] = "produto"
        elif "quantidade" in col:
            mapa[col] = "quantidade"
        elif "preço" in col or "preco" in col:
            mapa[col] = "preco"
        elif "local" in col:
            mapa[col] = "localidade"
        elif "data" in col:
            mapa[col] = "data"
        elif "mes" in col or "mês" in col:
            mapa[col] = "mes"

    df = df.rename(columns=mapa)

    return df

# ---------------------------
# CONVERTER MÊS PARA DATA
# ---------------------------
def converter_mes_para_data(df):
    meses_map = {
        "jan": 1, "fev": 2, "mar": 3, "abr": 4,
        "mai": 5, "jun": 6, "jul": 7, "ago": 8,
        "set": 9, "out": 10, "nov": 11, "dez": 12
    }

    if "data" in df.columns and df["data"].notna().any():
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        return df

    if "mes" in df.columns:
        print("📅 Convertendo 'mes' para data...")

        def parse_mes(valor):
            if pd.isna(valor):
                return None

            v = str(valor).lower().strip()

            # caso seja número (1,2,3...)
            if v.isdigit():
                return pd.Timestamp(year=2025, month=int(v), day=1)

            # caso seja nome (jan, fev...)
            for k in meses_map:
                if k in v:
                    return pd.Timestamp(year=2025, month=meses_map[k], day=1)

            return None

        df["data"] = df["mes"].apply(parse_mes)

    return df

# ---------------------------
# UPLOAD
# ---------------------------
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "logado" not in session:
        return redirect("/")

    if request.method == "POST":
        file = request.files.get("file")

        if file and file.filename != "":
            os.makedirs("uploads", exist_ok=True)
            caminho = os.path.join("uploads", file.filename)
            file.save(caminho)

            try:
                print("📊 Lendo Excel...")
                df = pd.read_excel(caminho, engine="openpyxl")

                print("📌 Colunas originais:", df.columns.tolist())

                # 🔥 MAPEAMENTO INTELIGENTE
                df = mapear_colunas(df)

                print("🧠 Colunas mapeadas:", df.columns.tolist())

                # 🔥 CONVERTE MÊS/DATA
                df = converter_mes_para_data(df)

                print("📅 Datas:", df["data"].head())

                # 🔥 GARANTE COLUNAS PADRÃO
                colunas_padrao = ["produtor", "produto", "quantidade", "preco", "localidade", "data"]

                for col in colunas_padrao:
                    if col not in df.columns:
                        df[col] = None

                # 🔥 REMOVE COLUNAS EXTRAS (ESSA LINHA RESOLVE SEU ERRO)
                df = df[colunas_padrao]

                print("✅ Colunas finais:", df.columns.tolist())

                # 🔥 CONVERSÕES
                df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce").fillna(0)
                df["preco"] = pd.to_numeric(df["preco"], errors="coerce").fillna(0)
                df["data"] = pd.to_datetime(df["data"], errors="coerce")

                # 🔥 LIMPA LINHAS RUINS
                df = df.dropna(subset=["produto"])

                # 🔥 SALVA
                conn = sqlite3.connect(DB)
                df.to_sql("producao", conn, if_exists="append", index=False)
                conn.close()

                print("✅ Dados inseridos com sucesso")

            except Exception as e:
                print("❌ ERRO:")
                traceback.print_exc()
                return f"Erro ao processar: {str(e)}"

            return redirect("/dashboard")

    return render_template("upload.html")

# ---------------------------
# LIMPAR BANCO (RESET)
# ---------------------------
@app.route("/reset", methods=["POST"])
def reset():
    if "logado" not in session:
        return redirect("/")

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    try:
        # 🔥 APAGA TODOS OS DADOS
        cursor.execute("DELETE FROM producao")

        # 🔥 opcional: resetar ID
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='producao'")

        conn.commit()
    except Exception as e:
        return f"Erro ao limpar banco: {str(e)}"
    finally:
        conn.close()

    return redirect("/upload")

# ---------------------------
# DASHBOARD
# ---------------------------
@app.route("/dashboard")
def dashboard():
    if "logado" not in session:
        return redirect("/")

    conn = sqlite3.connect(DB)
    df = pd.read_sql("SELECT * FROM producao", conn)
    conn.close()

    if not df.empty:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df["mes"] = df["data"].dt.month
        df["ano"] = df["data"].dt.year

    data = df.fillna("").to_dict(orient="records")

    return render_template("index.html", dados=data)

# ---------------------------
# LOGOUT
# ---------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------------------
# RUN
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)