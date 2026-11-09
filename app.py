from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__, template_folder='plantillas')

# ==========================================
# CONFIGURACIÓN INTELIGENTE DE BASE DE DATOS
# ==========================================
database_url = os.environ.get('DATABASE_URL')

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
elif os.name == 'nt':  
    # En tu PC (Windows): Conexión local a PostgreSQL con tu contraseña
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://postgres:Ca20402543@localhost/hospital_db'
else:  
    # En Render (Linux): SQLite automático para evitar fallos de red
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospital.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'hospital_jose_gregorio_hernandez_secret_key'
db = SQLAlchemy(app)

# ==========================================
# 1. MODELOS DE LA BASE DE DATOS
# ==========================================

class Administrador(db.Model):
    __tablename__ = 'administrador'
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

class Cita(db.Model):
    __tablename__ = 'cita'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    especialidad = db.Column(db.String(50), nullable=False)
    mensaje = db.Column(db.Text, nullable=False)
    doctor = db.Column(db.String(120), nullable=True)
    fecha_cita = db.Column(db.String(80), nullable=True)
    codigo_localizador = db.Column(db.String(20), nullable=True)
    estado = db.Column(db.String(20), default='Pendiente', nullable=False)

# Crear tablas y registrar automáticamente el superusuario de consultas
with app.app_context():
    db.create_all()
    admin_user = Administrador.query.filter_by(usuario="ConsultasHDJGH").first()
    if not admin_user:
        nuevo_admin = Administrador(
            usuario="ConsultasHDJGH",
            password=generate_password_hash("HDJGH123")
        )
        db.session.add(nuevo_admin)
        db.session.commit()

# ==========================================
# 2. FUNCIÓN PARA ENVÍO DE CORREOS AUTOMÁTICOS
# ==========================================

def enviar_correo_cita(cita):
    remitente = "carlosvalera15.02@gmail.com"
    password = "udxb rkqh yysn velh"
    
    destinatario = cita.email
    asunto = f"¡Cita Asignada! - Hospital Dr. José Gregorio Hernández [{cita.codigo_localizador}]"
    
    cuerpo = f"""
    Estimado/a {cita.nombre},
    
    Nos complace informarle que su solicitud de cita médica en el Hospital Dr. José Gregorio Hernández ha sido procesada y asignada exitosamente.
    
    Detalles de su cita:
    --------------------------------------------------
    📌 Código Localizador: {cita.codigo_localizador}
    🩺 Especialidad: {cita.especialidad}
    👨‍⚕️ Doctor Asignado: {cita.doctor}
    📅 Fecha Asignada: {cita.fecha_cita}
    📋 Estado: {cita.estado}
    --------------------------------------------------
    
    Por favor, conserve su código localizador y preséntese puntualmente el día indicado en el horario de consultas externas.
    
    Atentamente,
    Departamento de Admisión y Historias Médicas
    Hospital Dr. José Gregorio Hernández - Trujillo, Venezuela
    """
    
    mensaje = MIMEMultipart()
    mensaje['From'] = remitente
    mensaje['To'] = destinatario
    mensaje['Subject'] = asunto
    mensaje.attach(MIMEText(cuerpo, 'plain'))
    
    try:
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(remitente, password)
        servidor.sendmail(remitente, destinatario, mensaje.as_string())
        servidor.quit()
        return True
    except Exception as e:
        print(f"Error al enviar el correo: {e}")
        return False

# ==========================================
# 3. RUTAS PÚBLICAS DEL SITIO WEB
# ==========================================

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        especialidad = request.form.get('especialidad')
        mensaje = request.form.get('mensaje')

        if not nombre or not email or not especialidad or not mensaje:
            flash('Por favor, complete todos los campos del formulario.', 'error')
        else:
            localizador = f"HDJGH-{uuid.uuid4().hex[:6].upper()}"
            
            nueva_cita = Cita(
                nombre=nombre,
                email=email,
                especialidad=especialidad,
                mensaje=mensaje,
                codigo_localizador=localizador,
                estado='Pendiente'
            )
            db.session.add(nueva_cita)
            db.session.commit()
            
            flash(f'¡Solicitud enviada con éxito! Su código de seguimiento es: {localizador}', 'success')
            return redirect(url_for('index') + '#contacto')

    return render_template('index.html')

# ==========================================
# 4. RUTAS DEL PANEL DE ADMINISTRACIÓN
# ==========================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        user = request.form.get('usuario')
        pwd = request.form.get('password')

        admin = Administrador.query.filter_by(usuario=user).first()
        if admin and check_password_hash(admin.password, pwd):
            session['admin'] = admin.usuario
            flash('¡Bienvenido al panel de administración!', 'success')
            return redirect(url_for('panel_admin'))
        else:
            flash('Usuario o contraseña incorrectos.', 'error')

    return render_template('admin_login.html')

@app.route('/admin/panel')
def panel_admin():
    if 'admin' not in session:
        flash('Debe iniciar sesión para acceder al panel de control.', 'error')
        return redirect(url_for('admin_login'))

    citas = Cita.query.all()
    return render_template('admin_panel.html', citas=citas)

@app.route('/admin/editar/<int:id>', methods=['GET', 'POST'])
def editar_cita(id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    cita = Cita.query.get_or_404(id)

    if request.method == 'POST':
        cita.doctor = request.form.get('doctor')
        fecha_input = request.form.get('fecha_cita')
        cita.estado = request.form.get('estado')

        if fecha_input:
            citas_en_fecha = Cita.query.filter(Cita.fecha_cita == fecha_input, Cita.id != cita.id).count()
            
            if citas_en_fecha >= 8:
                flash(f'⚠️ El día {fecha_input} ya alcanzó el límite máximo de 8 citas. Por favor, elija otra fecha.', 'error')
                return render_template('admin_editar.html', cita=cita)
            
            cita.fecha_cita = fecha_input

        db.session.commit()
        
        try:
            correo_enviado = enviar_correo_cita(cita)
            if correo_enviado:
                flash('¡Cita asignada exitosamente y correo enviado al paciente!', 'success')
            else:
                flash('⚠️ Cita guardada, pero falló el envío del correo electrónico.', 'error')
        except Exception as e:
            flash('⚠️ Cita guardada correctamente en la base de datos.', 'success')

        return redirect(url_for('panel_admin'))

    if not cita.fecha_cita:
        fecha_actual = datetime.now()
        fecha_candidata = fecha_actual + timedelta(days=1)
        
        while fecha_candidata.weekday() >= 5:
            fecha_candidata += timedelta(days=1)

        while True:
            fecha_str = fecha_candidata.strftime('%Y-%m-%d')
            conteo = Cita.query.filter_by(fecha_cita=fecha_str).count()
            
            if conteo < 8:
                cita.fecha_cita = fecha_str
                break
            else:
                fecha_candidata += timedelta(days=1)
                while fecha_candidata.weekday() >= 5:
                    fecha_candidata += timedelta(days=1)

    return render_template('admin_editar.html', cita=cita)

@app.route('/admin/eliminar/<int:id>', methods=['POST'])
def eliminar_cita(id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    cita = Cita.query.get_or_404(id)
    db.session.delete(cita)
    db.session.commit()
    
    flash('🗑️ Cita eliminada del sistema exitosamente.', 'success')
    return redirect(url_for('panel_admin'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('Sesión cerrada correctamente.', 'success')
    return redirect(url_for('admin_login'))

# ==========================================
# 5. INICIO DE LA APLICACIÓN
# ==========================================
if __name__ == '__main__':
    app.run(debug=True)