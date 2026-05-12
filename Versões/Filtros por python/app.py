from flask import Flask, request, redirect, session, render_template, jsonify
import pandas as pd
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "segredo123"

# LOGIN SIMPLES
USER = "admin"
PASS = "123"


# =========================
# GARANTE BANCO + TABELA
# =========================
def init_db():
    conn = sqlite3.connect("meu_banco.db")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS vendas (
        produto TEXT,
        produtor TEXT,
        localidade TEXT,
        quantidade INTEGER,
        valor REAL,
        mes TEXT,
        beneficiamento TEXT
    )
    """)

    conn.close()


# =========================
# FUNÇÃO PARA LER BANCO
# =========================
def get_df():
    init_db()

    conn = sqlite3.connect("meu_banco.db")

    try:
        df = pd.read_sql_query("SELECT * FROM vendas", conn)
    except:
        df = pd.DataFrame(columns=[
            "produto", "produtor", "localidade",
            "quantidade", "valor", "mes", "beneficiamento"
        ])

    conn.close()
    return df


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["user"] == USER and request.form["password"] == PASS:
            session["logado"] = True
            return redirect("/")
        return "Login inválido"
    return render_template("login.html")


# =========================
# HOME
# =========================
@app.route("/")
def home():
    if "logado" not in session:
        return redirect("/login")
    return render_template("index.html")


# =========================
# UPLOAD EXCEL
# =========================
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "logado" not in session:
        return redirect("/login")

    if request.method == "POST":
        file = request.files["file"]

        if file:
            os.makedirs("uploads", exist_ok=True)
            caminho = os.path.join("uploads", file.filename)
            file.save(caminho)

            df = pd.read_excel(caminho)

            # padronizar colunas
            df.columns = [c.strip().lower() for c in df.columns]

            df = df.rename(columns={
                "preço": "preco",
                "preco": "preco",
                "mês": "mes",
                "mes": "mes",
                "benefiamento": "beneficiamento",
                "beneficiamento": "beneficiamento"
            })

            # =========================
            # LIMPEZA DE DADOS
            # =========================

            # preco
            df["preco"] = df["preco"].astype(str)\
                .str.replace("R$", "", regex=False)\
                .str.replace(",", ".")\
                .str.strip()

            df["preco"] = pd.to_numeric(df["preco"], errors="coerce")

            # quantidade
            df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce")

            # remover inválidos
            df = df.dropna(subset=["preco", "quantidade"])

            # valor
            df["valor"] = df["preco"] * df["quantidade"]

            # padronizar texto (CRUCIAL)
            for col in ["produto", "produtor", "mes", "localidade", "beneficiamento"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()

            # =========================
            # BANCO
            # =========================
            init_db()
            conn = sqlite3.connect("meu_banco.db")

            conn.execute("DELETE FROM vendas")

            df[[
                "produto",
                "produtor",
                "localidade",
                "quantidade",
                "valor",
                "mes",
                "beneficiamento"
            ]].to_sql("vendas", conn, if_exists="append", index=False)

            conn.close()

            return redirect("/")

    return render_template("upload.html")


# =========================
# FILTROS DINÂMICOS
# =========================
@app.route("/filtros")
def filtros():
    df = get_df()

    if len(df) == 0:
        return jsonify({
            "produtos": [],
            "produtores": [],
            "meses": []
        })

    return jsonify({
        "produtos": sorted(df["produto"].dropna().unique().tolist()),
        "produtores": sorted(df["produtor"].dropna().unique().tolist()),
        "meses": sorted(df["mes"].dropna().unique().tolist())
    })


# =========================
# DADOS COM FILTROS
# =========================
@app.route("/dados")
def dados():
    df = get_df()

    print("\n====== DEBUG INÍCIO ======")
    print("Total de linhas:", len(df))

    produto = request.args.get("produto")
    produtor = request.args.get("produtor")
    mes = request.args.get("mes")

    # padronizar dataframe
    for col in ["produto", "produtor", "mes"]:
        df[col] = df[col].astype(str).str.strip().str.lower()

    # =========================
    # FILTROS
    # =========================

    if produto:
        produto = produto.strip().lower()
        antes = len(df)
        df = df[df["produto"] == produto]
        print(f"Filtro produto: {produto} | {antes} -> {len(df)}")

    if produtor:
        produtor = produtor.strip().lower()
        antes = len(df)
        df = df[df["produtor"] == produtor]
        print(f"Filtro produtor: {produtor} | {antes} -> {len(df)}")

    if mes:
        mes = mes.strip().lower()
        antes = len(df)
        df = df[df["mes"].str.contains(mes)]
        print(f"Filtro mes: {mes} | {antes} -> {len(df)}")

    print("Total após filtros:", len(df))
    print("====== DEBUG FIM ======\n")

    # =========================
    # KPIs
    # =========================
    kpis = {
        "localidades": df["localidade"].nunique(),
        "produtores": df["produtor"].nunique(),
        "produtos": df["produto"].nunique(),
        "beneficiamentos": df["beneficiamento"].nunique(),
        "faturamento": float(df["valor"].sum()) if len(df) > 0 else 0
    }

    # =========================
    # GRÁFICOS
    # =========================
    g1 = df.groupby("produtor")["quantidade"].sum().reset_index() if len(df) > 0 else pd.DataFrame()
    g2 = df.groupby("produto")["valor"].sum().reset_index() if len(df) > 0 else pd.DataFrame()

    return jsonify({
        "kpis": kpis,
        "g1": g1.to_dict(orient="records"),
        "g2": g2.to_dict(orient="records"),
    })


# =========================
# START
# =========================
if __name__ == "__main__":
    init_db()
    app.run(debug=True)