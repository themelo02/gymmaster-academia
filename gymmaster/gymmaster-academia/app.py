import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import time
import hashlib
import re

# Configuração da página
st.set_page_config(
    page_title="GymMaster - Gestor de Academia",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Classe para gerenciar autenticação


class AuthManager:
    def __init__(self, db_name='academia.db'):
        self.db_name = db_name
        self.init_auth_database()

    def init_auth_database(self):
        """Inicializa tabela de usuários"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                telefone TEXT,
                senha_hash TEXT NOT NULL,
                data_criacao DATE DEFAULT CURRENT_DATE,
                data_atualizacao DATE DEFAULT CURRENT_DATE,
                tipo TEXT DEFAULT 'admin'
            )
        ''')

        conn.commit()
        conn.close()

    def hash_password(self, password):
        """Cria hash da senha"""
        return hashlib.sha256(password.encode()).hexdigest()

    def verificar_senha(self, password, hash_password):
        """Verifica se a senha está correta"""
        return self.hash_password(password) == hash_password

    def criar_usuario(self, nome, email, telefone, senha):
        """Cria um novo usuário"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            senha_hash = self.hash_password(senha)
            cursor.execute('''
                INSERT INTO usuarios (nome, email, telefone, senha_hash)
                VALUES (?, ?, ?, ?)
            ''', (nome, email, telefone, senha_hash))

            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Email já existe
        finally:
            conn.close()

    def verificar_login(self, email, senha):
        """Verifica credenciais de login"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, nome, email, telefone, senha_hash, tipo 
            FROM usuarios WHERE email = ?
        ''', (email,))

        usuario = cursor.fetchone()
        conn.close()

        if usuario and self.verificar_senha(senha, usuario[4]):
            return {
                'id': usuario[0],
                'nome': usuario[1],
                'email': usuario[2],
                'telefone': usuario[3],
                'tipo': usuario[5]
            }
        return None

    def atualizar_usuario(self, usuario_id, nome, telefone, email, senha_atual=None, nova_senha=None):
        """Atualiza dados do usuário"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            if senha_atual and nova_senha:
                # Verificar senha atual
                cursor.execute(
                    'SELECT senha_hash FROM usuarios WHERE id = ?', (usuario_id,))
                resultado = cursor.fetchone()

                if not resultado or not self.verificar_senha(senha_atual, resultado[0]):
                    return False, "Senha atual incorreta"

                # Atualizar com nova senha
                nova_senha_hash = self.hash_password(nova_senha)
                cursor.execute('''
                    UPDATE usuarios 
                    SET nome = ?, telefone = ?, email = ?, senha_hash = ?, data_atualizacao = CURRENT_DATE
                    WHERE id = ?
                ''', (nome, telefone, email, nova_senha_hash, usuario_id))
            else:
                # Atualizar sem mudar senha
                cursor.execute('''
                    UPDATE usuarios 
                    SET nome = ?, telefone = ?, email = ?, data_atualizacao = CURRENT_DATE
                    WHERE id = ?
                ''', (nome, telefone, email, usuario_id))

            conn.commit()
            return True, "Dados atualizados com sucesso"

        except sqlite3.IntegrityError:
            return False, "Email já está em uso"
        finally:
            conn.close()

# Classe para gerenciar o banco de dados principal


class DatabaseManager:
    def __init__(self, db_name='academia.db'):
        self.db_name = db_name
        self.init_database()
        self.migrate_database()

    def init_database(self):
        """Inicializa o banco de dados com tabelas"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Tabela de atletas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS atletas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                telefone TEXT,
                email TEXT,
                data_cadastro DATE DEFAULT CURRENT_DATE,
                data_vencimento DATE,
                status TEXT DEFAULT 'ativo',
                observacoes TEXT,
                plano TEXT DEFAULT 'Mensal',
                valor_plano REAL DEFAULT 10000.00
            )
        ''')

        # Tabela de pagamentos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pagamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                atleta_id INTEGER,
                data_pagamento DATE DEFAULT CURRENT_DATE,
                valor REAL,
                mes_referencia TEXT,
                forma_pagamento TEXT,
                observacoes TEXT,
                FOREIGN KEY(atleta_id) REFERENCES atletas(id)
            )
        ''')

        # Tabela de configurações e metas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configuracoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT UNIQUE,
                valor TEXT,
                data_atualizacao DATE DEFAULT CURRENT_DATE
            )
        ''')

        conn.commit()
        conn.close()

    def migrate_database(self):
        """Adiciona colunas faltantes nas tabelas existentes"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            # Verificar se a coluna data_nascimento existe
            cursor.execute("PRAGMA table_info(atletas)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'data_nascimento' not in columns:
                cursor.execute(
                    'ALTER TABLE atletas ADD COLUMN data_nascimento DATE')
                print("✅ Coluna data_nascimento adicionada")

            # Inserir meta padrão se não existir
            cursor.execute(
                "SELECT * FROM configuracoes WHERE chave = 'meta_receita_mensal'")
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO configuracoes (chave, valor) VALUES ('meta_receita_mensal', '500000')")

            conn.commit()

        except Exception as e:
            print(f"⚠️ Erro na migração: {e}")
        finally:
            conn.close()

    def get_connection(self):
        """Retorna conexão com o banco"""
        return sqlite3.connect(self.db_name)

    def add_atleta(self, nome, telefone, email, data_nascimento, data_vencimento, plano, valor_plano, observacoes=""):
        """Adiciona um novo atleta"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO atletas (nome, telefone, email, data_nascimento, data_vencimento, plano, valor_plano, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nome, telefone, email, data_nascimento, data_vencimento, plano, valor_plano, observacoes))

        conn.commit()
        atleta_id = cursor.lastrowid
        conn.close()

        return atleta_id

    def update_atleta(self, atleta_id, nome, telefone, email, data_nascimento, data_vencimento, plano, valor_plano, observacoes):
        """Atualiza os dados de um atleta"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE atletas 
            SET nome = ?, telefone = ?, email = ?, data_nascimento = ?, 
                data_vencimento = ?, plano = ?, valor_plano = ?, observacoes = ?
            WHERE id = ?
        ''', (nome, telefone, email, data_nascimento, data_vencimento, plano, valor_plano, observacoes, atleta_id))

        conn.commit()
        conn.close()

        return True

    def excluir_atleta(self, atleta_id):
        """Exclui um atleta e todos os seus pagamentos"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Primeiro excluir pagamentos (por causa da chave estrangeira)
            cursor.execute(
                "DELETE FROM pagamentos WHERE atleta_id = ?", (atleta_id,))

            # Depois excluir o atleta
            cursor.execute("DELETE FROM atletas WHERE id = ?", (atleta_id,))

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_all_atletas(self):
        """Retorna todos os atletas"""
        conn = self.get_connection()
        df = pd.read_sql("SELECT * FROM atletas ORDER BY nome", conn)
        conn.close()
        return df

    def get_atleta_by_id(self, atleta_id):
        """Retorna um atleta específico"""
        conn = self.get_connection()
        df = pd.read_sql("SELECT * FROM atletas WHERE id = ?",
                         conn, params=(atleta_id,))
        conn.close()
        return df.iloc[0] if not df.empty else None

    def update_atleta_status(self):
        """Atualiza status dos atletas baseado na data de vencimento"""
        conn = self.get_connection()
        cursor = conn.cursor()

        hoje = datetime.now().date()

        cursor.execute('''
            UPDATE atletas SET status = 
            CASE 
                WHEN date(data_vencimento) < date(?) THEN 'vencido'
                WHEN date(data_vencimento) <= date(?, '+7 days') THEN 'alerta'
                ELSE 'ativo'
            END
        ''', (hoje, hoje))

        conn.commit()
        conn.close()

    def registrar_pagamento(self, atleta_id, data_pagamento, valor, mes_referencia, forma_pagamento, observacoes):
        """Registra um novo pagamento"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO pagamentos (atleta_id, data_pagamento, valor, mes_referencia, forma_pagamento, observacoes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (atleta_id, data_pagamento, valor, mes_referencia, forma_pagamento, observacoes))

            # Atualizar data de vencimento do atleta
            atleta = self.get_atleta_by_id(atleta_id)
            if atleta is not None:
                plano = atleta['plano']

                meses_adicional = 1
                if plano == "Trimestral":
                    meses_adicional = 3
                elif plano == "Semestral":
                    meses_adicional = 6
                elif plano == "Anual":
                    meses_adicional = 12

                data_base = max(
                    datetime.now().date(),
                    datetime.strptime(
                        atleta['data_vencimento'], '%Y-%m-%d').date()
                )

                nova_data_vencimento = data_base + \
                    timedelta(days=30 * meses_adicional)

                cursor.execute('''
                    UPDATE atletas SET data_vencimento = ? WHERE id = ?
                ''', (nova_data_vencimento.strftime('%Y-%m-%d'), atleta_id))

            conn.commit()
            pagamento_id = cursor.lastrowid
            return pagamento_id

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_pagamentos(self, atleta_id=None):
        """Retorna pagamentos, opcionalmente filtrado por atleta"""
        conn = self.get_connection()

        if atleta_id:
            df = pd.read_sql('''
                SELECT p.*, a.nome as atleta_nome 
                FROM pagamentos p 
                JOIN atletas a ON p.atleta_id = a.id 
                WHERE p.atleta_id = ?
                ORDER BY p.data_pagamento DESC
            ''', conn, params=(atleta_id,))
        else:
            df = pd.read_sql('''
                SELECT p.*, a.nome as atleta_nome 
                FROM pagamentos p 
                JOIN atletas a ON p.atleta_id = a.id 
                ORDER BY p.data_pagamento DESC
            ''', conn)

        conn.close()
        return df

    def get_estatisticas_avancadas(self):
        """Retorna estatísticas avançadas para dashboard"""
        conn = self.get_connection()

        # Receita do mês atual
        mes_atual = datetime.now().strftime('%Y-%m')
        df_receita_mes = pd.read_sql('''
            SELECT SUM(valor) as receita_mes_atual
            FROM pagamentos 
            WHERE strftime('%Y-%m', data_pagamento) = ?
        ''', conn, params=(mes_atual,))

        # Receita mês anterior
        mes_anterior = (datetime.now().replace(day=1) -
                        timedelta(days=1)).strftime('%Y-%m')
        df_receita_mes_anterior = pd.read_sql('''
            SELECT SUM(valor) as receita_mes_anterior
            FROM pagamentos 
            WHERE strftime('%Y-%m', data_pagamento) = ?
        ''', conn, params=(mes_anterior,))

        # Receita últimos 12 meses
        df_receita_12_meses = pd.read_sql('''
            SELECT strftime('%Y-%m', data_pagamento) as mes,
                   SUM(valor) as receita_mensal,
                   COUNT(*) as total_pagamentos
            FROM pagamentos
            WHERE date(data_pagamento) >= date('now', '-12 months')
            GROUP BY mes
            ORDER BY mes
        ''', conn)

        # Estatísticas de atletas
        df_atletas_stats = pd.read_sql('''
            SELECT 
                COUNT(*) as total_atletas,
                SUM(CASE WHEN status = 'ativo' THEN 1 ELSE 0 END) as ativos,
                SUM(CASE WHEN status = 'vencido' THEN 1 ELSE 0 END) as vencidos,
                SUM(CASE WHEN status = 'alerta' THEN 1 ELSE 0 END) as alertas,
                AVG(valor_plano) as ticket_medio
            FROM atletas
        ''', conn)

        conn.close()

        receita_mes_atual = df_receita_mes.iloc[0]['receita_mes_atual'] or 0
        receita_mes_anterior = df_receita_mes_anterior.iloc[0]['receita_mes_anterior'] or 0

        # Calcular crescimento
        crescimento = 0
        if receita_mes_anterior > 0:
            crescimento = (
                (receita_mes_atual - receita_mes_anterior) / receita_mes_anterior) * 100

        return {
            'receita_mes_atual': receita_mes_atual,
            'receita_mes_anterior': receita_mes_anterior,
            'crescimento': crescimento,
            'receita_12_meses': df_receita_12_meses,
            'total_atletas': df_atletas_stats.iloc[0]['total_atletas'] or 0,
            'ativos': df_atletas_stats.iloc[0]['ativos'] or 0,
            'vencidos': df_atletas_stats.iloc[0]['vencidos'] or 0,
            'alertas': df_atletas_stats.iloc[0]['alertas'] or 0,
            'ticket_medio': df_atletas_stats.iloc[0]['ticket_medio'] or 0
        }

    def get_meta_receita(self):
        """Retorna a meta de receita mensal"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT valor FROM configuracoes WHERE chave = 'meta_receita_mensal'")
        result = cursor.fetchone()

        conn.close()

        return float(result[0]) if result else 500000.0

    def set_meta_receita(self, valor):
        """Define a meta de receita mensal"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO configuracoes (chave, valor, data_atualizacao)
            VALUES ('meta_receita_mensal', ?, CURRENT_DATE)
        ''', (str(valor),))

        conn.commit()
        conn.close()

    def get_notificacoes(self):
        """Retorna notificações do sistema"""
        conn = self.get_connection()

        hoje = datetime.now().date()

        # Notificações de vencimento
        df_alertas = pd.read_sql('''
            SELECT nome, data_vencimento, status
            FROM atletas 
            WHERE date(data_vencimento) <= date(?, '+7 days')
            AND status != 'vencido'
            ORDER BY data_vencimento ASC
        ''', conn, params=(hoje,))

        notificacoes = []

        # Notificações de vencimento
        for _, atleta in df_alertas.iterrows():
            dias_vencimento = (datetime.strptime(
                atleta['data_vencimento'], '%Y-%m-%d').date() - hoje).days
            if dias_vencimento < 0:
                notificacoes.append(f"❌ {atleta['nome']} - Vencido")
            elif dias_vencimento == 0:
                notificacoes.append(f"⚠️ {atleta['nome']} - Vence hoje!")
            else:
                notificacoes.append(
                    f"🔔 {atleta['nome']} - Vence em {dias_vencimento} dias")

        # Notificação de meta (se houver dados)
        stats = self.get_estatisticas_avancadas()
        meta = self.get_meta_receita()
        receita_atual = stats['receita_mes_atual']

        if receita_atual > 0:
            percentual_meta = (receita_atual / meta) * 100
            if percentual_meta >= 100:
                notificacoes.append(
                    f"🎯 Meta mensal atingida! ({percentual_meta:.1f}%)")
            elif percentual_meta >= 80:
                notificacoes.append(f"📈 Meta mensal: {percentual_meta:.1f}%")

        conn.close()
        return notificacoes


# Inicializar managers
auth_manager = AuthManager()
db = DatabaseManager()

# Funções de autenticação


def show_login():
    """Exibe tela de login"""
    st.title("🏋️ GymMaster - Login")
    st.markdown("---")

    # Verificar se é primeiro acesso
    conn = sqlite3.connect('academia.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    count_usuarios = cursor.fetchone()[0]
    conn.close()

    if count_usuarios == 0:
        st.info(
            "👋 **Primeiro acesso!** Cadastre-se para criar sua conta de administrador.")
        show_cadastro_primeiro_usuario()
        return

    tab1, tab2 = st.tabs(["🔐 Login", "📝 Cadastrar"])

    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="seu@email.com")
            senha = st.text_input("Senha", type="password",
                                  placeholder="Sua senha")

            if st.form_submit_button("🚀 Entrar"):
                if email and senha:
                    usuario = auth_manager.verificar_login(email, senha)
                    if usuario:
                        st.session_state['usuario'] = usuario
                        st.session_state['logged_in'] = True
                        st.success(f"Bem-vindo, {usuario['nome']}!")
                        st.rerun()
                    else:
                        st.error("Email ou senha incorretos!")
                else:
                    st.error("Preencha todos os campos!")

    with tab2:
        st.info("📝 **Cadastrar nova conta de administrador**")
        show_cadastro_usuario()


def show_cadastro_primeiro_usuario():
    """Exibe cadastro para primeiro usuário"""
    with st.form("primeiro_cadastro"):
        st.subheader("👑 Criar Conta de Administrador")

        nome = st.text_input("Nome Completo*", placeholder="Seu nome completo")
        email = st.text_input("Email*", placeholder="seu@email.com")
        telefone = st.text_input("Telefone", placeholder="(XX) XXXXX-XXXX")
        senha = st.text_input("Senha*", type="password",
                              placeholder="Crie uma senha forte")
        confirmar_senha = st.text_input(
            "Confirmar Senha*", type="password", placeholder="Digite a senha novamente")

        if st.form_submit_button("👑 Criar Conta Admin"):
            if not all([nome, email, senha, confirmar_senha]):
                st.error("Preencha todos os campos obrigatórios!")
            elif senha != confirmar_senha:
                st.error("As senhas não coincidem!")
            elif len(senha) < 6:
                st.error("A senha deve ter pelo menos 6 caracteres!")
            else:
                sucesso = auth_manager.criar_usuario(
                    nome, email, telefone, senha)
                if sucesso:
                    st.success(
                        "✅ Conta criada com sucesso! Faça login para continuar.")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("❌ Este email já está em uso!")


def show_cadastro_usuario():
    """Exibe cadastro para novos usuários"""
    with st.form("cadastro_usuario"):
        nome = st.text_input("Nome Completo*", placeholder="Seu nome completo")
        email = st.text_input("Email*", placeholder="seu@email.com")
        telefone = st.text_input("Telefone", placeholder="(XX) XXXXX-XXXX")
        senha = st.text_input("Senha*", type="password",
                              placeholder="Crie uma senha forte")
        confirmar_senha = st.text_input(
            "Confirmar Senha*", type="password", placeholder="Digite a senha novamente")

        if st.form_submit_button("📝 Cadastrar"):
            if not all([nome, email, senha, confirmar_senha]):
                st.error("Preencha todos os campos obrigatórios!")
            elif senha != confirmar_senha:
                st.error("As senhas não coincidem!")
            elif len(senha) < 6:
                st.error("A senha deve ter pelo menos 6 caracteres!")
            else:
                sucesso = auth_manager.criar_usuario(
                    nome, email, telefone, senha)
                if sucesso:
                    st.success(
                        "✅ Conta criada com sucesso! Faça login para continuar.")
                else:
                    st.error("❌ Este email já está em uso!")


def show_perfil():
    """Exibe e permite editar perfil do usuário"""
    st.header("👤 Meu Perfil")

    usuario = st.session_state['usuario']

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Informações Pessoais")

        with st.form("editar_perfil"):
            nome = st.text_input("Nome Completo*", value=usuario['nome'])
            email = st.text_input("Email*", value=usuario['email'])
            telefone = st.text_input(
                "Telefone", value=usuario['telefone'] or "")

            st.markdown("---")
            st.subheader("Alterar Senha")
            st.info("Deixe em branco para manter a senha atual")

            senha_atual = st.text_input(
                "Senha Atual", type="password", placeholder="Para confirmar alterações")
            nova_senha = st.text_input(
                "Nova Senha", type="password", placeholder="Deixe em branco para não alterar")
            confirmar_senha = st.text_input(
                "Confirmar Nova Senha", type="password", placeholder="Confirme a nova senha")

            if st.form_submit_button("💾 Salvar Alterações"):
                # Validar dados
                if not nome or not email:
                    st.error("Nome e email são obrigatórios!")
                    return

                if nova_senha:
                    if not senha_atual:
                        st.error("Digite a senha atual para alterar a senha!")
                        return
                    if nova_senha != confirmar_senha:
                        st.error("As novas senhas não coincidem!")
                        return
                    if len(nova_senha) < 6:
                        st.error(
                            "A nova senha deve ter pelo menos 6 caracteres!")
                        return

                sucesso, mensagem = auth_manager.atualizar_usuario(
                    usuario['id'], nome, telefone, email, senha_atual, nova_senha
                )

                if sucesso:
                    st.success("✅ " + mensagem)
                    # Atualizar sessão
                    st.session_state['usuario']['nome'] = nome
                    st.session_state['usuario']['email'] = email
                    st.session_state['usuario']['telefone'] = telefone
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("❌ " + mensagem)

    with col2:
        st.subheader("Informações da Conta")

        st.info(f"""
        **ID:** {usuario['id']}  
        **Tipo:** {usuario['tipo']}  
        **Email:** {usuario['email']}
        """)

        # Estatísticas do usuário (opcional)
        st.markdown("---")
        st.subheader("📊 Estatísticas")

        df_atletas = db.get_all_atletas()
        df_pagamentos = db.get_pagamentos()

        st.metric("Total de Atletas", len(df_atletas))
        st.metric("Total de Pagamentos", len(df_pagamentos))

        # Botão de logout
        st.markdown("---")
        if st.button("🚪 Sair", type="primary"):
            st.session_state.clear()
            st.rerun()

# Função para verificar autenticação


def verificar_autenticacao():
    """Verifica se o usuário está autenticado"""
    if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
        show_login()
        return False
    return True

# Interface principal (após login)


def main_app():
    """Interface principal após login"""
    usuario = st.session_state['usuario']

    st.title(f"🏋️ GymMaster - Olá, {usuario['nome']}!")
    st.markdown("---")

    # Atualizar status automaticamente
    db.update_atleta_status()

    # Menu lateral com notificações
    with st.sidebar:
        st.title("📋 Menu")

        # Informações do usuário
        st.info(f"👤 {usuario['nome']}")

        # Seção de notificações
        notificacoes = db.get_notificacoes()
        if notificacoes:
            st.subheader("🔔 Notificações")
            for notificacao in notificacoes[:5]:
                st.info(notificacao)
            if len(notificacoes) > 5:
                st.caption(f"... e mais {len(notificacoes) - 5} notificações")
            st.markdown("---")

        menu = st.selectbox(
            "Navegação",
            ["📊 Dashboard Interativo", "Cadastrar Atleta", "Listar/Editar Atletas",
                "💰 Pagamentos", "Relatórios Financeiros", "⚙️ Configurações", "👤 Meu Perfil"]
        )

    # Páginas
    if menu == "📊 Dashboard Interativo":
        show_dashboard_interativo()
    elif menu == "Cadastrar Atleta":
        show_cadastro_atleta()
    elif menu == "Listar/Editar Atletas":
        show_lista_editar_atletas()  # type: ignore # type: ignore
    elif menu == "💰 Pagamentos":
        show_pagamentos()
    elif menu == "Relatórios Financeiros":
        show_relatorios_financeiros()
    elif menu == "⚙️ Configurações":
        show_configuracoes()
    elif menu == "👤 Meu Perfil":
        show_perfil()

# (MANTER TODAS AS OUTRAS FUNÇÕES EXISTENTES: show_dashboard_interativo, show_cadastro_atleta, show_lista_editar_atletas, show_pagamentos, show_relatorios_financeiros, show_configuracoes)
# [Inserir aqui todas as outras funções que já existiam anteriormente...]


def show_dashboard_interativo():
    """Exibe dashboard interativo simplificado"""
    st.header("📊 Dashboard Interativo")

    # Carregar estatísticas
    stats = db.get_estatisticas_avancadas()
    meta_receita = db.get_meta_receita()

    # KPIs principais
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        receita_mes = stats['receita_mes_atual']
        percentual_meta = (receita_mes / meta_receita) * \
            100 if meta_receita > 0 else 0
        st.metric(
            "💰 Receita Mensal",
            f"KZ {receita_mes:,.2f}",
            f"{percentual_meta:.1f}% da meta",
            delta_color="normal" if percentual_meta >= 70 else "inverse"
        )

    with col2:
        crescimento = stats['crescimento']
        st.metric(
            "📈 Crescimento",
            f"{crescimento:+.1f}%",
            f"vs mês anterior",
            delta_color="normal" if crescimento >= 0 else "inverse"
        )

    with col3:
        st.metric("👥 Atletas Ativos", stats['ativos'])

    with col4:
        st.metric("💵 Ticket Médio", f"KZ {stats['ticket_medio']:,.2f}")

    st.markdown("---")

    # Gráficos - APENAS evolução da receita
    st.subheader("📈 Evolução da Receita (12 meses)")

    if not stats['receita_12_meses'].empty:
        fig_receita = px.line(
            stats['receita_12_meses'],
            x='mes',
            y='receita_mensal',
            markers=True,
            title="Receita Mensal dos Últimos 12 Meses"
        )
        fig_receita.update_layout(
            xaxis_title="Mês",
            yaxis_title="Receita (KZ)",
            showlegend=False,
            height=400
        )

        # Adicionar linha da meta
        fig_receita.add_hline(
            y=meta_receita,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Meta: KZ {meta_receita:,.0f}"
        )

        st.plotly_chart(fig_receita, use_container_width=True)
    else:
        st.info("📊 Aguardando dados para mostrar evolução...")

    # Status dos atletas - mantido pois é útil
    st.subheader("📊 Status dos Atletas")

    status_data = {
        'Status': ['Ativos', 'Em Alerta', 'Vencidos'],
        'Quantidade': [stats['ativos'], stats['alertas'], stats['vencidos']]
    }
    df_status = pd.DataFrame(status_data)

    fig_status = px.bar(
        df_status,
        x='Status',
        y='Quantidade',
        color='Status',
        color_discrete_map={
            'Ativos': '#2ecc71',
            'Em Alerta': '#f39c12',
            'Vencidos': '#e74c3c'
        },
        height=300
    )

    st.plotly_chart(fig_status, use_container_width=True)

    # Métricas avançadas
    st.markdown("---")
    st.subheader("📈 Métricas Avançadas")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        taxa_retencao = (stats['ativos'] / stats['total_atletas']
                         * 100) if stats['total_atletas'] > 0 else 0
        st.metric("🔄 Taxa de Retenção", f"{taxa_retencao:.1f}%")

    with col2:
        churn_rate = (stats['vencidos'] / stats['total_atletas']
                      * 100) if stats['total_atletas'] > 0 else 0
        st.metric("📉 Churn Rate", f"{churn_rate:.1f}%")

    with col3:
        receita_total_estimada = stats['ativos'] * stats['ticket_medio']
        st.metric("💰 Receita Mensal Estimada",
                  f"KZ {receita_total_estimada:,.2f}")

    with col4:
        # Auto-refresh
        if st.button("🔄 Atualizar Dados"):
            st.rerun()

# [Inserir aqui as outras funções existentes: show_cadastro_atleta, show_lista_editar_atletas, show_pagamentos, show_relatorios_financeiros, show_configuracoes]
# ... (manter o código dessas funções igual ao anterior)


def show_cadastro_atleta():
    """Exibe formulário de cadastro de atletas"""
    st.header("➕ Cadastrar Novo Atleta")

    with st.form("cadastro_atleta", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            nome = st.text_input(
                "Nome Completo*", placeholder="Ex: João Silva")
            telefone = st.text_input("Telefone", placeholder="(XX) XXXXX-XXXX")
            email = st.text_input("Email", placeholder="exemplo@email.com")

        with col2:
            plano = st.selectbox(
                "Plano*", ["Mensal", "Trimestral", "Semestral", "Anual"])
            valor_plano = st.number_input(
                "Valor do Plano (KZ)*", min_value=0.0, value=10000.0, step=1000.0)
            data_vencimento = st.date_input(
                "Data de Vencimento*", min_value=datetime.now().date())

        data_nascimento = st.date_input("Data de Nascimento (opcional)",
                                        max_value=datetime.now().date(),
                                        value=None)

        observacoes = st.text_area(
            "Observações", placeholder="Informações adicionais...")

        submitted = st.form_submit_button("💾 Cadastrar Atleta")

        if submitted:
            if nome and data_vencimento and valor_plano > 0:
                try:
                    atleta_id = db.add_atleta(
                        nome=nome,
                        telefone=telefone,
                        email=email,
                        data_nascimento=data_nascimento.strftime(
                            '%Y-%m-%d') if data_nascimento else None,
                        data_vencimento=data_vencimento.strftime('%Y-%m-%d'),
                        plano=plano,
                        valor_plano=valor_plano,
                        observacoes=observacoes
                    )

                    st.success(
                        f"✅ Atleta **{nome}** cadastrado com sucesso! ID: {atleta_id}")
                    st.balloons()

                except Exception as e:
                    st.error(f"❌ Erro ao cadastrar atleta: {e}")
            else:
                st.error("⚠️ Preencha todos os campos obrigatórios (*)")

# [Continuar com as outras funções...]

# Função principal


def main():
    """Função principal da aplicação"""
    if not verificar_autenticacao():
        return

    main_app()


if __name__ == "__main__":
    main()
