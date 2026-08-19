from flask import Flask, jsonify, request, session, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os, json

app = Flask(__name__)
app.secret_key = os.environ.get('CLAVE_SECRETA', 'impulso-secreto-2026')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True

CORS(app, supports_credentials=True, origins='*')

db_url = os.environ.get('DATABASE_URL', 'sqlite:///impulso.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Pedido(db.Model):
    __tablename__ = 'pedidos_v3'
    id         = db.Column(db.Integer, primary_key=True)
    folio      = db.Column(db.String(30))
    tipo_venta = db.Column(db.String(30))
    tipo_prod  = db.Column(db.String(20), default='marcos')  # marcos | arte
    cli        = db.Column(db.String(100))
    tel        = db.Column(db.String(20))
    suc        = db.Column(db.String(50))
    vend       = db.Column(db.String(50))
    fecha      = db.Column(db.String(20))
    mes        = db.Column(db.Integer)
    items      = db.Column(db.Text)
    sub        = db.Column(db.Float, default=0)
    total      = db.Column(db.Float, default=0)
    met        = db.Column(db.String(30))
    ant        = db.Column(db.Float, default=0)
    rest       = db.Column(db.Float, default=0)
    obs        = db.Column(db.String(300))
    est        = db.Column(db.String(30), default='Pendiente')
    entrega    = db.Column(db.String(20))
    taller_est = db.Column(db.String(30))
    casillero  = db.Column(db.String(30))
    factura_num = db.Column(db.String(30))

class Movimiento(db.Model):
    __tablename__ = 'movimientos_v3'
    id          = db.Column(db.Integer, primary_key=True)
    tipo        = db.Column(db.String(20))
    concepto    = db.Column(db.String(100))
    desc        = db.Column(db.String(200))
    monto       = db.Column(db.Float, default=0)
    fecha       = db.Column(db.String(20))
    mes         = db.Column(db.Integer)
    suc         = db.Column(db.String(50))
    cuenta      = db.Column(db.String(50))
    cta_destino = db.Column(db.String(50))
    socio       = db.Column(db.String(50))

# ── USUARIOS EN BD ────────────────────────────────────────────────────────────

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id       = db.Column(db.Integer, primary_key=True)
    key      = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    name     = db.Column(db.String(100))
    display  = db.Column(db.String(50))
    role     = db.Column(db.String(20), default='venta')
    suc      = db.Column(db.String(50))

USUARIOS_SEED = [
    {'key':'jardines',  'password':'jardines123', 'name':'Alondra',   'display':'Jardines',  'role':'venta', 'suc':'Jardines'},
    {'key':'zibata',    'password':'zibata123',   'name':'Zibata',    'display':'Zibata',    'role':'venta', 'suc':'Zibata'},
    {'key':'admin',     'password':'admin123',    'name':'Ana Karen', 'display':'Admin',     'role':'admin', 'suc':'Admin'},
    {'key':'estefania', 'password':'impulso2026', 'name':'Estefania', 'display':'Estefania', 'role':'owner', 'suc':'Admin'},
    {'key':'taller',    'password':'taller2026',  'name':'Taller',    'display':'Taller',    'role':'taller','suc':'Taller'},
]
USUARIOS_PROTEGIDOS = ('admin', 'estefania')  # no se pueden borrar

def usr_dict(u, incluir_pwd=False):
    d = {'id':u.id,'key':u.key,'name':u.name,'display':u.display,'role':u.role,'suc':u.suc}
    if incluir_pwd:
        d['pwd'] = u.password
    return d

def seed_usuarios():
    """Inserta los usuarios base solo si no existen. Nunca pisa contraseñas ya cambiadas."""
    for s in USUARIOS_SEED:
        if not Usuario.query.filter_by(key=s['key']).first():
            db.session.add(Usuario(**s))
    db.session.commit()
    # AUTO-RESCATE: el sistema no puede quedarse sin dueña. Si ninguna cuenta tiene
    # rol owner (p.ej. se degradó por accidente al editarla), se restaura estefania.
    if not Usuario.query.filter_by(role='owner').first():
        u = Usuario.query.filter_by(key='estefania').first()
        if u:
            u.role = 'owner'
            u.display = 'Estefania'
            u.suc = 'Admin'
            db.session.commit()

# ── EMPLEADOS EN BD ───────────────────────────────────────────────────────────

class Empleado(db.Model):
    __tablename__ = 'empleados'
    id      = db.Column(db.Integer, primary_key=True)
    nombre  = db.Column(db.String(100), nullable=False)
    puesto  = db.Column(db.String(100))
    suc     = db.Column(db.String(50))
    ingreso = db.Column(db.String(20))
    salario = db.Column(db.Float, default=0)
    metpago = db.Column(db.String(50))
    banco   = db.Column(db.String(100))
    curp    = db.Column(db.String(30))
    rfc     = db.Column(db.String(20))
    tel     = db.Column(db.String(30))
    dir     = db.Column(db.String(300))
    diapago    = db.Column(db.String(15), default='')          # dia de la semana en que se le paga
    estatus    = db.Column(db.String(20), default='activo')   # activo | baja
    fecha_baja = db.Column(db.String(20), default='')

def emp_dict(e):
    return {'id':e.id,'nombre':e.nombre,'puesto':e.puesto,'suc':e.suc,
            'ingreso':e.ingreso,'salario':e.salario,'metpago':e.metpago,
            'banco':e.banco,'curp':e.curp,'rfc':e.rfc,'tel':e.tel,'dir':e.dir,
            'diapago':e.diapago or '','estatus':e.estatus or 'activo','fecha_baja':e.fecha_baja or ''}

# ── HELPERS DE AUTORIZACIÓN ───────────────────────────────────────────────────

def requiere_login(f):
    from functools import wraps
    @wraps(f)
    def decorado(*args, **kwargs):
        if not session.get('usuario'):
            return jsonify({'error': 'No autenticado'}), 401
        return f(*args, **kwargs)
    return decorado

def requiere_admin(f):
    """Solo admin u owner."""
    from functools import wraps
    @wraps(f)
    def decorado(*args, **kwargs):
        if not session.get('usuario'):
            return jsonify({'error': 'No autenticado'}), 401
        if session.get('rol') not in ('admin', 'owner'):
            return jsonify({'error': 'Sin permisos'}), 403
        return f(*args, **kwargs)
    return decorado

def serve_static(filename):
    # Try multiple folder names
    for folder in ['static', 'estático', 'estatico']:
        path = os.path.join(BASE_DIR, folder, filename)
        if os.path.exists(path):
            return send_from_directory(os.path.join(BASE_DIR, folder), filename)
    return jsonify({'error': f'{filename} no encontrado'}), 404

@app.route('/')
def index():
    return serve_static('index.html')

@app.route('/cotizador')
def cotizador():
    return serve_static('Cotizador_Impulso.html')

@app.route('/cotizador-movil')
def cotizador_movil():
    return serve_static('cotizador_movil.html')

@app.route('/sw-cotizador.js')
def sw_cotizador():
    return serve_static('sw-cotizador.js')

# ── AUTH (contra la BD) ───────────────────────────────────────────────────────

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    key = data.get('key', '').strip()
    pwd = data.get('pwd', '').strip()
    u = Usuario.query.filter_by(key=key).first()
    if u and u.password == pwd:
        session.permanent = True
        session['usuario'] = key
        session['suc'] = u.suc
        session['rol'] = u.role
        return jsonify({'ok': True, 'user': usr_dict(u, incluir_pwd=True)})
    return jsonify({'ok': False, 'msg': 'Credenciales incorrectas'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/me')
def me():
    key = session.get('usuario')
    if not key:
        return jsonify({'ok': False}), 401
    u = Usuario.query.filter_by(key=key).first()
    if not u:
        session.clear()
        return jsonify({'ok': False}), 401
    return jsonify({'ok': True, 'user': usr_dict(u)})

# ── CRUD USUARIOS ─────────────────────────────────────────────────────────────

@app.route('/api/usuarios', methods=['GET'])
def get_usuarios():
    # Sin sesión: lista sanitizada (para las tarjetas de login).
    # Con sesión admin/owner: incluye contraseña (para el modal de edición).
    es_gestor = session.get('rol') in ('admin', 'owner')
    usuarios = Usuario.query.order_by(Usuario.id).all()
    return jsonify([usr_dict(u, incluir_pwd=es_gestor) for u in usuarios])

@app.route('/api/usuarios', methods=['POST'])
@requiere_admin
def crear_usuario():
    d = request.json or {}
    key = (d.get('key') or '').strip().lower()
    pwd = (d.get('pwd') or '').strip()
    if not key or not pwd or not d.get('name'):
        return jsonify({'error': 'Faltan campos'}), 400
    if Usuario.query.filter_by(key=key).first():
        return jsonify({'error': 'Ya existe un usuario con ese login'}), 400
    # Solo la dueña puede crear otros owners
    if d.get('role') == 'owner' and session.get('rol') != 'owner':
        return jsonify({'error': 'Solo la dueña puede crear usuarios owner'}), 403
    u = Usuario(key=key, password=pwd, name=d.get('name'),
                display=d.get('display', d.get('suc','')),
                role=d.get('role','venta'), suc=d.get('suc',''))
    db.session.add(u)
    db.session.commit()
    return jsonify(usr_dict(u, incluir_pwd=True)), 201

@app.route('/api/usuarios/<int:uid>', methods=['PUT'])
@requiere_admin
def actualizar_usuario(uid):
    u = Usuario.query.get_or_404(uid)
    # Solo la dueña puede modificar cuentas owner
    if u.role == 'owner' and session.get('rol') != 'owner':
        return jsonify({'error': 'Solo la dueña puede modificar esta cuenta'}), 403
    d = request.json or {}
    if 'role' in d and d['role'] == 'owner' and session.get('rol') != 'owner':
        return jsonify({'error': 'Solo la dueña puede asignar rol owner'}), 403
    # Candado: no se puede degradar al único owner (el sistema quedaría sin dueña)
    if u.role == 'owner' and d.get('role') and d['role'] != 'owner':
        if Usuario.query.filter_by(role='owner').count() <= 1:
            return jsonify({'error': 'No se puede quitar el rol de Dueña: es la única cuenta owner del sistema'}), 400
    nueva_key = (d.get('key') or u.key).strip().lower()
    if nueva_key != u.key:
        if u.key in USUARIOS_PROTEGIDOS:
            return jsonify({'error': 'No se puede cambiar el login de este usuario base'}), 400
        if Usuario.query.filter_by(key=nueva_key).first():
            return jsonify({'error': 'Ya existe un usuario con ese login'}), 400
        u.key = nueva_key
    for campo in ['name', 'display', 'role', 'suc']:
        if campo in d:
            setattr(u, campo, d[campo])
    if d.get('pwd'):
        u.password = d['pwd'].strip()
    db.session.commit()
    return jsonify(usr_dict(u, incluir_pwd=True))

@app.route('/api/usuarios/<int:uid>', methods=['DELETE'])
@requiere_admin
def borrar_usuario(uid):
    u = Usuario.query.get_or_404(uid)
    if u.key in USUARIOS_PROTEGIDOS:
        return jsonify({'error': 'Este usuario no se puede eliminar'}), 400
    if u.role == 'owner' and session.get('rol') != 'owner':
        return jsonify({'error': 'Solo la dueña puede eliminar cuentas owner'}), 403
    db.session.delete(u)
    db.session.commit()
    return jsonify({'ok': True})

# ── CRUD EMPLEADOS ────────────────────────────────────────────────────────────

@app.route('/api/empleados', methods=['GET'])
@requiere_login
def get_empleados():
    return jsonify([emp_dict(e) for e in Empleado.query.order_by(Empleado.id).all()])

@app.route('/api/empleados', methods=['POST'])
@requiere_admin
def crear_empleado():
    d = request.json or {}
    if not d.get('nombre'):
        return jsonify({'error': 'Nombre requerido'}), 400
    e = Empleado(nombre=d.get('nombre'), puesto=d.get('puesto',''),
                 suc=d.get('suc',''), ingreso=d.get('ingreso',''),
                 salario=d.get('salario',0), metpago=d.get('metpago',''),
                 banco=d.get('banco',''), curp=d.get('curp',''),
                 rfc=d.get('rfc',''), tel=d.get('tel',''), dir=d.get('dir',''),
                 diapago=d.get('diapago',''),
                 estatus=d.get('estatus','activo'), fecha_baja=d.get('fecha_baja',''))
    db.session.add(e)
    db.session.commit()
    return jsonify(emp_dict(e)), 201

@app.route('/api/empleados/<int:eid>', methods=['PUT'])
@requiere_admin
def actualizar_empleado(eid):
    e = Empleado.query.get_or_404(eid)
    d = request.json or {}
    for campo in ['nombre','puesto','suc','ingreso','salario','metpago','banco','curp','rfc','tel','dir','diapago','estatus','fecha_baja']:
        if campo in d:
            setattr(e, campo, d[campo])
    db.session.commit()
    return jsonify(emp_dict(e))

@app.route('/api/empleados/<int:eid>', methods=['DELETE'])
@requiere_admin
def borrar_empleado(eid):
    e = Empleado.query.get_or_404(eid)
    db.session.delete(e)
    db.session.commit()
    return jsonify({'ok': True})

# ── PEDIDOS ───────────────────────────────────────────────────────────────────

@app.route('/api/pedidos', methods=['GET'])
@requiere_login
def get_pedidos():
    # Todos los roles reciben el concentrado completo: las vistas por sucursal
    # (Pedidos, CxC, Mi Dia) filtran en el frontend, y Ordenes de Compra
    # necesita ambas sucursales para que quien pida, pida todo.
    q = Pedido.query
    return jsonify([p_dict(p) for p in q.order_by(Pedido.id.desc()).all()])

@app.route('/api/pedidos', methods=['POST'])
@requiere_login
def crear_pedido():
    d = request.json or {}
    p = Pedido(
        folio=d.get('folio'), tipo_venta=d.get('tipo_venta','general'), tipo_prod=d.get('tipo_prod','marcos'),
        cli=d.get('cli'), tel=d.get('tel'),
        suc=d.get('suc', session.get('suc')), vend=d.get('vend'),
        fecha=d.get('fecha'), mes=d.get('mes'),
        items=json.dumps(d.get('items',[])),
        sub=d.get('sub',0), total=d.get('total',0),
        met=d.get('met'), ant=d.get('ant',0), rest=d.get('rest',0),
        obs=d.get('obs'), est=d.get('est','Pendiente'), entrega=d.get('entrega'),
        taller_est=d.get('taller_est','Por pedir'), casillero=d.get('casillero','')
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(p_dict(p)), 201

@app.route('/api/pedidos/<int:pid>', methods=['PUT'])
@requiere_login
def actualizar_pedido(pid):
    p = Pedido.query.get_or_404(pid)
    d = request.json or {}
    for campo in ['folio','tipo_venta','tipo_prod','cli','tel','suc','vend','fecha','mes','sub','total','met','ant','rest','obs','est','entrega','taller_est','casillero','factura_num']:
        if campo in d:
            setattr(p, campo, d[campo])
    if 'items' in d:
        p.items = json.dumps(d['items'])
    db.session.commit()
    return jsonify(p_dict(p))

@app.route('/api/pedidos/<int:pid>', methods=['DELETE'])
@requiere_login
def borrar_pedido(pid):
    p = Pedido.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'ok': True})

def p_dict(p):
    return {
        'id':p.id,'folio':p.folio,'tipo_venta':p.tipo_venta,'tipo_prod':p.tipo_prod or 'marcos',
        'cli':p.cli,'tel':p.tel,'suc':p.suc,'vend':p.vend,
        'fecha':p.fecha,'mes':p.mes,
        'items':json.loads(p.items) if p.items else [],
        'sub':p.sub,'total':p.total,'met':p.met,
        'ant':p.ant,'rest':p.rest,'obs':p.obs,
        'est':p.est,'entrega':p.entrega,
        'factura_num':p.factura_num or '',
        'taller_est':p.taller_est,'casillero':p.casillero
    }

# ── MOVIMIENTOS ───────────────────────────────────────────────────────────────

@app.route('/api/movimientos', methods=['GET'])
@requiere_login
def get_movimientos():
    rol = session.get('rol')
    suc = session.get('suc')
    q = Movimiento.query
    if rol not in ('admin','owner'):
        q = q.filter_by(suc=suc)
    return jsonify([m_dict(m) for m in q.order_by(Movimiento.id.desc()).all()])

@app.route('/api/movimientos', methods=['POST'])
@requiere_login
def crear_movimiento():
    d = request.json or {}
    m = Movimiento(
        tipo=d.get('tipo'), concepto=d.get('concepto'), desc=d.get('desc'),
        monto=d.get('monto',0), fecha=d.get('fecha'), mes=d.get('mes'),
        suc=d.get('suc', session.get('suc')),
        cuenta=d.get('cuenta'), cta_destino=d.get('cta_destino'), socio=d.get('socio','')
    )
    db.session.add(m)
    db.session.commit()
    return jsonify(m_dict(m)), 201

@app.route('/api/movimientos/<int:mid>', methods=['PUT'])
@requiere_login
def actualizar_movimiento(mid):
    m = Movimiento.query.get_or_404(mid)
    d = request.json or {}
    for campo in ['tipo','concepto','desc','monto','fecha','mes','suc','cuenta','cta_destino','socio']:
        if campo in d:
            setattr(m, campo, d[campo])
    db.session.commit()
    return jsonify(m_dict(m))

@app.route('/api/movimientos/<int:mid>', methods=['DELETE'])
@requiere_login
def borrar_movimiento(mid):
    m = Movimiento.query.get_or_404(mid)
    db.session.delete(m)
    db.session.commit()
    return jsonify({'ok': True})

def m_dict(m):
    return {
        'id':m.id,'tipo':m.tipo,'concepto':m.concepto,'desc':m.desc,
        'monto':m.monto,'fecha':m.fecha,'mes':m.mes,'suc':m.suc,
        'cuenta':m.cuenta,'cta_destino':m.cta_destino,'socio':m.socio
    }

# ── FACTURAS EN BD ────────────────────────────────────────────────────────────

class CuentaPagar(db.Model):
    __tablename__ = 'cxp'
    id            = db.Column(db.Integer, primary_key=True)
    proveedor     = db.Column(db.String(150), nullable=False)
    factura_num   = db.Column(db.String(60))     # folio de la factura del proveedor
    concepto      = db.Column(db.String(300))
    monto         = db.Column(db.Float, default=0)
    fecha_recibida= db.Column(db.String(20))
    fecha_vence   = db.Column(db.String(20))
    estatus       = db.Column(db.String(20), default='pendiente')  # pendiente | pagada
    fecha_pago    = db.Column(db.String(20))
    cuenta_pago   = db.Column(db.String(80))
    ref_pago      = db.Column(db.String(150))
    mov_id        = db.Column(db.Integer)        # enlace al movimiento de salida generado
    oc            = db.Column(db.String(40))     # orden de compra relacionada (opcional)

def cxp_dict(c):
    return {'id':c.id,'proveedor':c.proveedor,'factura_num':c.factura_num or '','concepto':c.concepto or '',
            'monto':c.monto or 0,'fecha_recibida':c.fecha_recibida or '','fecha_vence':c.fecha_vence or '',
            'estatus':c.estatus or 'pendiente','fecha_pago':c.fecha_pago or '','cuenta_pago':c.cuenta_pago or '',
            'ref_pago':c.ref_pago or '','mov_id':c.mov_id,'oc':c.oc or ''}

# ── LECTOR DE ESTADO DE CUENTA INBURSA (PDF) ─────────────────────────────────
MESES_EDO = {'ENE':1,'FEB':2,'MAR':3,'ABR':4,'MAY':5,'JUN':6,'JUL':7,'AGO':8,'SEP':9,'OCT':10,'NOV':11,'DIC':12}

@app.route('/api/edocta', methods=['POST'])
@requiere_admin
def leer_edocta():
    try:
        from pypdf import PdfReader
    except Exception:
        return jsonify({'error': 'Falta la librería pypdf en el servidor: agrega la línea "pypdf" a requirements.txt y vuelve a desplegar.'}), 500
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'No llegó ningún archivo'}), 400
    import re as _re, io
    try:
        reader = PdfReader(io.BytesIO(f.read()))
        texto = '\n'.join((p.extract_text() or '') for p in reader.pages)
    except Exception as e:
        return jsonify({'error': 'No pude leer el PDF: ' + str(e)}), 400
    # ── FORMATO 2: "Detalle de movimientos" (se descarga por rango de días) ──
    # Trae la fecha completa 17/08/2026 y el signo en el propio monto, en vez de
    # "AGO. 17" con saldo corrido. Se detecta y se procesa aparte.
    det_re = _re.compile(r'^(\d{2})/(\d{2})/(\d{4})\s+(.+?)\s+(\d{6,})\s+(-?[\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$')
    det_lineas = [l.strip() for l in texto.split('\n') if det_re.match(l.strip())]
    if len(det_lineas) >= 5:
        depositos, otros, cargos, n = [], [], [], 0
        for lin in det_lineas:
            g = det_re.match(lin)
            dia, mes, anio_l = int(g.group(1)), int(g.group(2)), int(g.group(3))
            concepto = g.group(4).strip()
            ref = g.group(5)
            monto = float(g.group(6).replace(',', ''))
            n += 1
            if monto <= 0:            # cargos: comisiones, transferencias enviadas, TDC
                cu2 = concepto.upper()
                # comision del banco = lo que cobra por operar, NO los pagos que ella hace.
                # Ojo: "TRANSFERENCIA - ENVIO - SPEI" es la comision de $4.50;
                # "TRANSFERENCIA SPEI" a secas es la transferencia de verdad.
                es_com = ('TASA DE DESCTO' in cu2 or 'TASA DESCUENTO' in cu2
                          or 'CUOTA MENSUAL' in cu2 or cu2.startswith('IVA')
                          or 'TRANSFERENCIA - ENVIO' in cu2)
                cargos.append({'fecha': '%04d-%02d-%02d' % (anio_l, mes, dia),
                               'monto': round(-monto, 2), 'det': concepto[:70],
                               'ref': ref, 'comision': es_com})
                continue
            fecha = '%04d-%02d-%02d' % (anio_l, mes, dia)
            cu = concepto.upper()
            if cu.startswith('LIQUIDACION ADQUIRENTE'):
                sub = 'AMEX' if 'AMEX' in cu else ('CREDITO' if 'CREDITO' in cu else 'DEBITO')
                depositos.append({'fecha': fecha, 'monto': monto, 'tipo': 'terminal', 'det': sub, 'terminal': ref})
            elif cu.startswith('DEPOSITO') or cu.startswith('TRASPASO DE ('):
                depositos.append({'fecha': fecha, 'monto': monto, 'tipo': 'spei',
                                  'det': concepto[:70], 'terminal': ref})
            else:
                otros.append({'fecha': fecha, 'monto': monto, 'det': concepto[:50] or 'abono'})
        msaldo = _re.search(r'Saldo\s+Saldo disponible', texto)
        sfin = None
        msf = _re.search(r'([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+0\s+0', texto)
        if msf:
            try: sfin = float(msf.group(1).replace(',', ''))
            except Exception: sfin = None
        fechas_ok = sorted(d['fecha'] for d in depositos + cargos if d.get('fecha'))
        return jsonify({'depositos': depositos, 'otros_abonos': otros, 'cargos': cargos,
                        'anio': anio_l if det_lineas else 2026, 'n_movs': n,
                        'saldo_final': sfin,
                        'desde': fechas_ok[0] if fechas_ok else None,
                        'hasta': fechas_ok[-1] if fechas_ok else None,
                        'formato': 'detalle_movimientos'})

    m = _re.search(r'Del\s+\d{1,2}\s+\w+\.?\s+(\d{4})', texto)
    anio = int(m.group(1)) if m else 2026
    ini = _re.compile(r'^([A-Z]{3})\.?\s+(\d{1,2})\s+(\d{6,})\s+(.*)$')
    lmonto = _re.compile(r'^\$?\s*([\d,]+\.\d{2})(?:\s+([\d,]+\.\d{2}))?\s*$')
    tailm = _re.compile(r'^(.*?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$')
    finre = _re.compile(r'RESUMEN GRAFICO|Tipo Comprobante|CONSULTAS Y RECLAMACIONES')
    movs, cur = [], None
    for lin in texto.split('\n'):
        lin = lin.strip()
        if not lin: continue
        if finre.search(lin): break
        mm = ini.match(lin)
        if mm and mm.group(1) in MESES_EDO:
            resto = mm.group(4).strip()
            cur = {'mes': MESES_EDO[mm.group(1)], 'dia': int(mm.group(2)), 'concepto': resto, 'extra': ''}
            tm = tailm.match(resto)  # caso: montos en la misma línea (ej. INTERESES GANADOS)
            if tm:
                cur['concepto'] = tm.group(1).strip()
                cur['monto'] = float(tm.group(2).replace(',', ''))
                cur['saldo'] = float(tm.group(3).replace(',', ''))
                movs.append(cur); cur = None
            continue
        lm = lmonto.match(lin)
        if lm and cur is not None:
            cur['monto'] = float(lm.group(1).replace(',', ''))
            cur['saldo'] = float(lm.group(2).replace(',', '')) if lm.group(2) else None
            movs.append(cur); cur = None
            continue
        if cur is not None:
            cur['extra'] += ' ' + lin
    saldo_prev = None
    m = _re.search(r'SALDO\s+ANTERIOR\s+([\d,]+\.\d{2})', texto)
    if m: saldo_prev = float(m.group(1).replace(',', ''))
    depositos, otros = [], []
    for mv in movs:
        monto, saldo = mv.get('monto'), mv.get('saldo')
        if monto is None: continue
        es = None
        if saldo_prev is not None and saldo is not None:
            if abs(saldo_prev + monto - saldo) < 0.02: es = True
            elif abs(saldo_prev - monto - saldo) < 0.02: es = False
        if es is None:
            cu = mv['concepto'].upper()
            es = cu.startswith('LIQUIDACION ADQUIRENTE') or cu.startswith('DEPOSITO') or cu.startswith('DEVOLUCION') or 'INTERESES' in cu
        if saldo is not None: saldo_prev = saldo
        if not es: continue
        fecha = '%04d-%02d-%02d' % (anio, mv['mes'], mv['dia'])
        cu = mv['concepto'].upper()
        if cu.startswith('LIQUIDACION ADQUIRENTE'):
            sub = 'AMEX' if 'AMEX' in cu else ('CREDITO' if 'CREDITO' in cu else 'DEBITO')
            t = _re.search(r'-(\d{6,})', mv['extra'])
            depositos.append({'fecha': fecha, 'monto': monto, 'tipo': 'terminal', 'det': sub, 'terminal': t.group(1) if t else ''})
        elif cu.startswith('DEPOSITO'):
            depositos.append({'fecha': fecha, 'monto': monto, 'tipo': 'spei', 'det': _re.sub(r'\s+', ' ', mv['extra']).strip()[:70] or 'DEPOSITO SPEI', 'terminal': ''})
        else:
            otros.append({'fecha': fecha, 'monto': monto, 'det': mv['concepto'][:50] or 'abono'})
    return jsonify({'depositos': depositos, 'otros_abonos': otros, 'anio': anio, 'n_movs': len(movs)})

@app.route('/api/cxp', methods=['GET'])
@requiere_admin
def get_cxp():
    return jsonify([cxp_dict(c) for c in CuentaPagar.query.order_by(CuentaPagar.id.desc()).all()])

@app.route('/api/cxp', methods=['POST'])
@requiere_admin
def crear_cxp():
    d = request.json or {}
    c = CuentaPagar(proveedor=d.get('proveedor','').strip(), factura_num=d.get('factura_num',''),
                    concepto=d.get('concepto',''), monto=d.get('monto',0),
                    fecha_recibida=d.get('fecha_recibida',''), fecha_vence=d.get('fecha_vence',''),
                    estatus='pendiente', oc=d.get('oc',''))
    if not c.proveedor:
        return jsonify({'error':'Falta el proveedor'}), 400
    db.session.add(c); db.session.commit()
    return jsonify(cxp_dict(c))

@app.route('/api/cxp/<int:cid>', methods=['PUT'])
@requiere_admin
def actualizar_cxp(cid):
    c = CuentaPagar.query.get_or_404(cid)
    d = request.json or {}
    for campo in ['proveedor','factura_num','concepto','monto','fecha_recibida','fecha_vence',
                  'estatus','fecha_pago','cuenta_pago','ref_pago','mov_id','oc']:
        if campo in d:
            setattr(c, campo, d[campo])
    db.session.commit()
    return jsonify(cxp_dict(c))

@app.route('/api/cxp/<int:cid>', methods=['DELETE'])
@requiere_admin
def borrar_cxp(cid):
    c = CuentaPagar.query.get_or_404(cid)
    db.session.delete(c); db.session.commit()
    return jsonify({'ok': True})

class Factura(db.Model):
    __tablename__ = 'facturas'
    id     = db.Column(db.Integer, primary_key=True)
    num    = db.Column(db.String(40), nullable=False)
    rfc    = db.Column(db.String(20))
    fecha  = db.Column(db.String(20))
    folios = db.Column(db.Text)          # JSON: lista de folios
    total  = db.Column(db.Float, default=0)

def fac_dict(f):
    return {'id':f.id,'num':f.num,'rfc':f.rfc,'fecha':f.fecha,
            'folios':json.loads(f.folios) if f.folios else [],'total':f.total}

@app.route('/api/facturas', methods=['GET'])
@requiere_login
def get_facturas():
    return jsonify([fac_dict(f) for f in Factura.query.order_by(Factura.id.desc()).all()])

@app.route('/api/facturas', methods=['POST'])
@requiere_login
def crear_factura():
    d = request.json or {}
    if not d.get('num'):
        return jsonify({'error': 'No. de factura requerido'}), 400
    f = Factura(num=d.get('num'), rfc=d.get('rfc',''), fecha=d.get('fecha',''),
                folios=json.dumps(d.get('folios',[])), total=d.get('total',0))
    db.session.add(f)
    db.session.commit()
    return jsonify(fac_dict(f)), 201

@app.route('/api/facturas/<int:fid>', methods=['DELETE'])
@requiere_login
def borrar_factura(fid):
    f = Factura.query.get_or_404(fid)
    db.session.delete(f)
    db.session.commit()
    return jsonify({'ok': True})

# ── CONFIG (clave-valor JSON, p.ej. conceptos del Estado de Resultados) ──────

class Config(db.Model):
    __tablename__ = 'config'
    clave = db.Column(db.String(50), primary_key=True)
    valor = db.Column(db.Text)

@app.route('/api/config/<clave>', methods=['GET'])
@requiere_login
def get_config(clave):
    c = Config.query.get(clave)
    return jsonify({'clave': clave, 'valor': json.loads(c.valor) if c and c.valor else None})

@app.route('/api/config/<clave>', methods=['PUT'])
@requiere_admin
def set_config(clave):
    d = request.json or {}
    c = Config.query.get(clave)
    if not c:
        c = Config(clave=clave)
        db.session.add(c)
    c.valor = json.dumps(d.get('valor'))
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/debug')
def debug():
    folders = os.listdir(BASE_DIR)
    return jsonify({'base_dir': BASE_DIR, 'files': folders})


@app.route('/api/import_pedidos', methods=['POST'])
def import_pedidos():
    data = request.json or {}
    secret = data.get('secret', '')
    if secret != 'impulso2026':
        return jsonify({'error': 'No autorizado'}), 401
    pedidos_data = data.get('pedidos', [])
    count = 0
    for d in pedidos_data:
        try:
            import json as _json
            p = Pedido(
                folio=d.get('folio'), tipo_venta=d.get('tipo_venta','general'), tipo_prod=d.get('tipo_prod','marcos'),
                cli=d.get('cli'), tel=d.get('tel'),
                suc=d.get('suc','Jardines'), vend=d.get('vend'),
                fecha=d.get('fecha'), mes=d.get('mes'),
                items=_json.dumps(d.get('items',[])),
                sub=d.get('sub',0), total=d.get('total',0),
                met=d.get('met','Efectivo'), ant=d.get('ant',0),
                rest=d.get('rest',0), obs=d.get('obs',''),
                est=d.get('est','Pendiente'), entrega=d.get('entrega','')
            )
            db.session.add(p)
            count += 1
        except Exception as e:
            pass
    db.session.commit()
    return jsonify({'ok': True, 'imported': count})





# ── CATÁLOGO DE MOLDURAS EN BD ────────────────────────────────────────────────

class Moldura(db.Model):
    __tablename__ = 'molduras'
    id           = db.Column(db.Integer, primary_key=True)
    nombre       = db.Column(db.String(150), nullable=False)
    precio_lista = db.Column(db.Float, default=0)
    desp_cm      = db.Column(db.Float, default=0)
    proveedor    = db.Column(db.String(50), default='PROPIO')
    estatus      = db.Column(db.String(20), default='activa')

def mol_dict(m):
    return {'id':m.id,'nombre':m.nombre,'precio_lista':m.precio_lista,
            'desp_cm':m.desp_cm,'proveedor':m.proveedor,'estatus':m.estatus}

@app.route('/api/molduras', methods=['GET'])
@requiere_login
def get_molduras():
    return jsonify([mol_dict(m) for m in Moldura.query.order_by(Moldura.id).all()])

@app.route('/api/molduras/bulk', methods=['POST'])
@requiere_admin
def seed_molduras():
    """Siembra inicial del catálogo (solo si la tabla está vacía)."""
    if Moldura.query.first():
        return jsonify({'error': 'El catálogo ya está sembrado'}), 400
    items = (request.json or {}).get('items', [])
    for it in items:
        db.session.add(Moldura(nombre=it.get('nombre',''), precio_lista=it.get('precio_lista',0),
                               desp_cm=it.get('desp_cm',0), proveedor=it.get('proveedor','PROPIO'),
                               estatus=it.get('estatus','activa')))
    db.session.commit()
    return jsonify({'ok': True, 'sembradas': len(items)}), 201

@app.route('/api/molduras', methods=['POST'])
@requiere_login
def crear_moldura():
    """Todos los roles logueados (incluye venta) pueden dar de alta molduras."""
    d = request.json or {}
    if not d.get('nombre'):
        return jsonify({'error': 'Nombre requerido'}), 400
    m = Moldura(nombre=d.get('nombre'), precio_lista=d.get('precio_lista',0),
                desp_cm=d.get('desp_cm',0), proveedor=d.get('proveedor','PROPIO'),
                estatus=d.get('estatus','activa'))
    db.session.add(m)
    db.session.commit()
    return jsonify(mol_dict(m)), 201

@app.route('/api/molduras/<int:mid>', methods=['PUT'])
@requiere_login
def actualizar_moldura(mid):
    """Todos los roles logueados (incluye venta) pueden editar molduras."""
    m = Moldura.query.get_or_404(mid)
    d = request.json or {}
    for campo in ['nombre','precio_lista','desp_cm','proveedor','estatus']:
        if campo in d:
            setattr(m, campo, d[campo])
    db.session.commit()
    return jsonify(mol_dict(m))

@app.route('/api/molduras/<int:mid>', methods=['DELETE'])
@requiere_admin
def borrar_moldura(mid):
    """Eliminar moldura (solo admin/owner) — para duplicados."""
    m = Moldura.query.get_or_404(mid)
    db.session.delete(m)
    db.session.commit()
    return jsonify({'ok': True})


# ── ABONOS (cobros con fecha: liquidaciones y pagos parciales) ────────────────

class Abono(db.Model):
    __tablename__ = 'abonos'
    id        = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer)
    folio     = db.Column(db.String(30))
    cli       = db.Column(db.String(100))
    suc       = db.Column(db.String(50))
    monto     = db.Column(db.Float, default=0)
    met       = db.Column(db.String(30))
    fecha     = db.Column(db.String(20))
    tipo      = db.Column(db.String(20), default='Abono')  # Abono | Liquidacion

def ab_dict(a):
    return {'id':a.id,'pedido_id':a.pedido_id,'folio':a.folio,'cli':a.cli,'suc':a.suc,
            'monto':a.monto,'met':a.met,'fecha':a.fecha,'tipo':a.tipo}

@app.route('/api/abonos', methods=['GET'])
@requiere_login
def get_abonos():
    abonos = Abono.query.order_by(Abono.id.desc()).limit(1000).all()
    return jsonify([ab_dict(a) for a in abonos])

@app.route('/api/abonos', methods=['POST'])
@requiere_login
def crear_abono():
    d = request.json or {}
    a = Abono(pedido_id=d.get('pedido_id'), folio=d.get('folio',''), cli=d.get('cli',''),
              suc=d.get('suc',''), monto=d.get('monto',0), met=d.get('met',''),
              fecha=d.get('fecha',''), tipo=d.get('tipo','Abono'))
    db.session.add(a)
    db.session.commit()
    return jsonify(ab_dict(a)), 201

@app.route('/api/abonos/<int:aid>', methods=['PUT'])
@requiere_admin
def actualizar_abono(aid):
    a = Abono.query.get_or_404(aid)
    d = request.json or {}
    for campo in ['monto', 'met', 'fecha', 'tipo']:
        if campo in d:
            setattr(a, campo, d[campo])
    db.session.commit()
    return jsonify(ab_dict(a))

@app.route('/api/abonos/<int:aid>', methods=['DELETE'])
@requiere_admin
def borrar_abono(aid):
    a = Abono.query.get_or_404(aid)
    db.session.delete(a)
    db.session.commit()
    return jsonify({'ok': True})


# ── ÓRDENES DE COMPRA (lotes pedidos a proveedores) ───────────────────────────

class OrdenCompra(db.Model):
    __tablename__ = 'ordenes_compra'
    id          = db.Column(db.Integer, primary_key=True)
    oc          = db.Column(db.String(20))  # folio: OC-0001
    prov        = db.Column(db.String(50))
    prov_nombre = db.Column(db.String(100))
    fecha       = db.Column(db.String(30))
    items       = db.Column(db.Text)  # JSON: [{mol,pzas,meds,fols}]

def ord_dict(o):
    return {'id':o.id,'oc':o.oc,'prov':o.prov,'prov_nombre':o.prov_nombre,'fecha':o.fecha,
            'items':json.loads(o.items) if o.items else []}

@app.route('/api/ordenes', methods=['GET'])
@requiere_login
def get_ordenes():
    return jsonify([ord_dict(o) for o in OrdenCompra.query.order_by(OrdenCompra.id.desc()).all()])

@app.route('/api/ordenes', methods=['POST'])
@requiere_login
def crear_orden():
    d = request.json or {}
    o = OrdenCompra(prov=d.get('prov',''), prov_nombre=d.get('prov_nombre',''),
                    fecha=d.get('fecha',''), items=json.dumps(d.get('items',[])))
    db.session.add(o)
    db.session.commit()
    o.oc = 'OC-%04d' % o.id  # folio consecutivo de orden de compra
    db.session.commit()
    return jsonify(ord_dict(o)), 201

@app.route('/api/ordenes/<int:oid>', methods=['PUT'])
@requiere_login
def actualizar_orden(oid):
    o = OrdenCompra.query.get_or_404(oid)
    d = request.json or {}
    if 'items' in d:
        o.items = json.dumps(d['items'])
    db.session.commit()
    return jsonify(ord_dict(o))

@app.route('/api/ordenes/<int:oid>', methods=['DELETE'])
@requiere_admin
def borrar_orden(oid):
    o = OrdenCompra.query.get_or_404(oid)
    db.session.delete(o)
    db.session.commit()
    return jsonify({'ok': True})


# ── PENDIENTES ────────────────────────────────────────────────────────────────

class Pendiente(db.Model):
    __tablename__ = 'pendientes'
    id        = db.Column(db.Integer, primary_key=True)
    desc      = db.Column(db.String(300))
    cliente   = db.Column(db.String(100))
    folio_ref = db.Column(db.String(50))
    asignado  = db.Column(db.String(100))
    fecha     = db.Column(db.String(20))
    est       = db.Column(db.String(30), default='abierto')
    suc       = db.Column(db.String(50))

def pend_dict(p):
    return {'id':p.id,'desc':p.desc,'cliente':p.cliente,'folio_ref':p.folio_ref,
            'asignado':p.asignado,'fecha':p.fecha,'est':p.est,'suc':p.suc}

@app.route('/api/pendientes', methods=['GET'])
@requiere_login
def get_pendientes():
    rol = session.get('rol')
    suc = session.get('suc')
    q = Pendiente.query
    if rol not in ('admin','owner','taller'):
        q = q.filter_by(suc=suc)
    return jsonify([pend_dict(p) for p in q.order_by(Pendiente.id.desc()).all()])

@app.route('/api/pendientes', methods=['POST'])
@requiere_login
def crear_pendiente():
    d = request.json or {}
    p = Pendiente(
        desc=d.get('desc'), cliente=d.get('cliente',''),
        folio_ref=d.get('folio_ref',''), asignado=d.get('asignado','Todos'),
        fecha=d.get('fecha'), est=d.get('est','abierto'),
        suc=d.get('suc', session.get('suc'))
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(pend_dict(p)), 201

@app.route('/api/pendientes/<int:pid>', methods=['PUT'])
@requiere_login
def actualizar_pendiente(pid):
    p = Pendiente.query.get_or_404(pid)
    d = request.json or {}
    for campo in ['desc','cliente','folio_ref','asignado','fecha','est','suc']:
        if campo in d:
            setattr(p, campo, d[campo])
    db.session.commit()
    return jsonify(pend_dict(p))

@app.route('/api/pendientes/<int:pid>', methods=['DELETE'])
@requiere_login
def borrar_pendiente(pid):
    p = Pendiente.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'ok': True})


# ── VENDEDORES ────────────────────────────────────────────────────────────────

class Vendedor(db.Model):
    __tablename__ = 'vendedores'
    id        = db.Column(db.Integer, primary_key=True)
    nombre    = db.Column(db.String(100))
    suc       = db.Column(db.String(50))
    comision  = db.Column(db.Float, default=0)        # % sobre marcos
    comision_arte = db.Column(db.Float, default=10)   # % sobre arte
    estatus   = db.Column(db.String(20), default='activo')

def vend_dict(v):
    return {'id':v.id,'nombre':v.nombre,'suc':v.suc,'comision':v.comision,'comision_arte':(v.comision_arte if v.comision_arte is not None else 10),'estatus':v.estatus}

@app.route('/api/vendedores', methods=['GET'])
@requiere_login
def get_vendedores():
    return jsonify([vend_dict(v) for v in Vendedor.query.order_by(Vendedor.nombre).all()])

@app.route('/api/vendedores', methods=['POST'])
@requiere_login
def crear_vendedor():
    d = request.json or {}
    v = Vendedor(nombre=d.get('nombre'), suc=d.get('suc',''), comision=d.get('comision',0), comision_arte=d.get('comision_arte',10), estatus=d.get('estatus','activo'))
    db.session.add(v)
    db.session.commit()
    return jsonify(vend_dict(v)), 201

@app.route('/api/vendedores/<int:vid>', methods=['PUT'])
@requiere_login
def actualizar_vendedor(vid):
    v = Vendedor.query.get_or_404(vid)
    d = request.json or {}
    for campo in ['nombre','suc','comision','comision_arte','estatus']:
        if campo in d:
            setattr(v, campo, d[campo])
    db.session.commit()
    return jsonify(vend_dict(v))

@app.route('/api/vendedores/<int:vid>', methods=['DELETE'])
@requiere_login
def borrar_vendedor(vid):
    v = Vendedor.query.get_or_404(vid)
    db.session.delete(v)
    db.session.commit()
    return jsonify({'ok': True})


# ── ACTIVITY LOG ──────────────────────────────────────────────────────────────

class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    id        = db.Column(db.Integer, primary_key=True)
    ts        = db.Column(db.String(30))
    user      = db.Column(db.String(50))
    user_name = db.Column(db.String(100))
    accion    = db.Column(db.String(100))
    detalle   = db.Column(db.String(300))

def act_dict(a):
    return {'id':a.id,'ts':a.ts,'user':a.user,'userName':a.user_name,'accion':a.accion,'detalle':a.detalle}

@app.route('/api/activity', methods=['GET'])
@requiere_login
def get_activity():
    logs = ActivityLog.query.order_by(ActivityLog.id.desc()).limit(200).all()
    return jsonify([act_dict(a) for a in logs])

@app.route('/api/activity', methods=['POST'])
@requiere_login
def post_activity():
    d = request.json or {}
    from datetime import datetime
    a = ActivityLog(
        ts=datetime.utcnow().isoformat(),
        user=session.get('usuario','?'),
        user_name=d.get('userName','?'),
        accion=d.get('accion',''),
        detalle=d.get('detalle','')
    )
    db.session.add(a)
    db.session.commit()
    return jsonify(act_dict(a)), 201

@app.route('/api/activity', methods=['DELETE'])
@requiere_login
def clear_activity():
    ActivityLog.query.delete()
    db.session.commit()
    return jsonify({'ok': True})

def migrar_columnas():
    """Agrega columnas nuevas a tablas existentes (create_all no altera tablas ya creadas)."""
    from sqlalchemy import text
    for stmt in [
        "ALTER TABLE pedidos_v3 ADD COLUMN IF NOT EXISTS taller_est VARCHAR(30)",
        "ALTER TABLE pedidos_v3 ADD COLUMN IF NOT EXISTS casillero VARCHAR(30)",
        "ALTER TABLE ordenes_compra ADD COLUMN IF NOT EXISTS oc VARCHAR(20)",
        "ALTER TABLE pedidos_v3 ADD COLUMN IF NOT EXISTS factura_num VARCHAR(30)",
        "ALTER TABLE empleados ADD COLUMN IF NOT EXISTS estatus VARCHAR(20) DEFAULT 'activo'",
        "ALTER TABLE empleados ADD COLUMN IF NOT EXISTS fecha_baja VARCHAR(20) DEFAULT ''",
        "ALTER TABLE pedidos_v3 ADD COLUMN IF NOT EXISTS tipo_prod VARCHAR(20) DEFAULT 'marcos'",
        "ALTER TABLE vendedores ADD COLUMN IF NOT EXISTS comision_arte FLOAT DEFAULT 10",
        "ALTER TABLE empleados ADD COLUMN IF NOT EXISTS diapago VARCHAR(15) DEFAULT ''",
    ]:
        try:
            db.session.execute(text(stmt)); db.session.commit()
        except Exception:
            db.session.rollback()
            try:  # SQLite local no soporta IF NOT EXISTS en columnas
                db.session.execute(text(stmt.replace(' IF NOT EXISTS',''))); db.session.commit()
            except Exception:
                db.session.rollback()



# ═══════════════════════════════════════════════════════════════════════════════
# REVISIÓN DE NOTAS FÍSICAS  ·  la foto de la nota manuscrita contra lo capturado
# ───────────────────────────────────────────────────────────────────────────────
# No se guarda ninguna foto: se lee, se compara y solo queda el resultado.
# Usa urllib de la librería estándar a propósito — no hace falta tocar
# requirements.txt ni instalar el SDK.
# Requiere la variable de entorno ANTHROPIC_API_KEY en Railway.
# ═══════════════════════════════════════════════════════════════════════════════

class RevNota(db.Model):
    __tablename__ = 'rev_notas'
    id       = db.Column(db.Integer, primary_key=True)
    folio    = db.Column(db.String(30))
    suc      = db.Column(db.String(30))
    fecha    = db.Column(db.String(20))     # día de la revisión
    veredicto= db.Column(db.String(20))     # cuadra | difiere | sin_pedido
    difs     = db.Column(db.Text)           # JSON con las diferencias
    lectura  = db.Column(db.Text)           # JSON con lo que se leyó de la foto
    quien    = db.Column(db.String(50))

def rev_dict(r):
    def _j(v):
        try: return json.loads(v) if v else None
        except Exception: return None
    return {'id': r.id, 'folio': r.folio, 'suc': r.suc, 'fecha': r.fecha,
            'veredicto': r.veredicto, 'difs': _j(r.difs), 'lectura': _j(r.lectura),
            'quien': r.quien}

INSTRUCCION_NOTA = """Esta es la foto de una nota de pedido escrita a mano de una galería de enmarcado en México.

Lee lo que ALCANCES A LEER y devuelve SOLO un objeto JSON, sin explicaciones, sin ```.

Estructura exacta:
{
  "folio": "número de nota o folio, como string, o null",
  "cliente": "nombre del cliente o null",
  "fecha": "fecha de la nota en formato AAAA-MM-DD, o null",
  "articulos": [
    {"moldura":"clave o nombre de la moldura","ancho":número en cm o null,
     "alto":número en cm o null,"cantidad":número,"extras":"texto o null"}
  ],
  "anticipo": número o null,
  "total": número o null,
  "ilegible": ["nombre de cada campo que no se pudo leer con seguridad"],
  "confianza": número del 0 al 100
}

Reglas:
- Si un dato no se ve o no estás seguro, pon null y agrégalo a "ilegible". NUNCA inventes.
- Las medidas suelen venir como 30x40 o 30 × 40 (ancho por alto) en centímetros.
- Los importes vienen en pesos mexicanos; devuélvelos como número sin $ ni comas.
- Si la foto no es una nota de pedido, devuelve {"error":"no es una nota"}."""

@app.route('/api/leer-nota', methods=['POST'])
@requiere_login
def leer_nota():
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return jsonify({'error': 'Falta la llave ANTHROPIC_API_KEY en las variables de entorno de Railway. '
                                 'Agrégala en Railway > Variables y vuelve a desplegar.'}), 500
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'No llegó ninguna foto'}), 400

    import base64, urllib.request, urllib.error
    raw = f.read()
    if len(raw) > 5 * 1024 * 1024:
        return jsonify({'error': 'La foto pesa más de 5 MB. Tómala de nuevo con menos resolución.'}), 400
    media = (f.mimetype or 'image/jpeg').lower()
    if media not in ('image/jpeg', 'image/png', 'image/webp', 'image/gif'):
        media = 'image/jpeg'

    payload = {
        'model': 'claude-sonnet-5',
        'max_tokens': 1500,
        'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': media,
                                         'data': base64.b64encode(raw).decode()}},
            {'type': 'text', 'text': INSTRUCCION_NOTA}
        ]}]
    }
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=json.dumps(payload).encode('utf-8'),
        headers={'content-type': 'application/json', 'x-api-key': api_key,
                 'anthropic-version': '2023-06-01'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try: det = e.read().decode('utf-8')[:300]
        except Exception: det = ''
        msg = 'La API de Anthropic respondió ' + str(e.code)
        if e.code == 401: msg = 'La llave ANTHROPIC_API_KEY no es válida o está vencida.'
        elif e.code == 429: msg = 'La API está saturada o se acabó el saldo. Espera un momento e intenta de nuevo.'
        return jsonify({'error': msg, 'detalle': det}), 502
    except Exception as e:
        return jsonify({'error': 'No se pudo contactar la API: ' + str(e)}), 502

    txt = ''.join(b.get('text', '') for b in data.get('content', []) if b.get('type') == 'text')
    limpio = txt.strip()
    if limpio.startswith('```'):
        limpio = limpio.split('```')[1] if '```' in limpio[3:] else limpio
        limpio = limpio.replace('json', '', 1).strip()
    try:
        lectura = json.loads(limpio)
    except Exception:
        return jsonify({'error': 'No se pudo interpretar la lectura de la foto', 'crudo': txt[:400]}), 502

    u = data.get('usage', {}) or {}
    return jsonify({'lectura': lectura,
                    'uso': {'entrada': u.get('input_tokens', 0), 'salida': u.get('output_tokens', 0)}})

@app.route('/api/revnotas', methods=['GET'])
@requiere_login
def get_revnotas():
    q = RevNota.query
    fecha = request.args.get('fecha')
    if fecha: q = q.filter(RevNota.fecha == fecha)
    return jsonify([rev_dict(r) for r in q.order_by(RevNota.id.desc()).limit(500).all()])

@app.route('/api/revnotas', methods=['POST'])
@requiere_login
def post_revnota():
    d = request.json or {}
    prev = RevNota.query.filter_by(folio=str(d.get('folio') or ''), fecha=d.get('fecha')).first()
    r = prev or RevNota()
    r.folio     = str(d.get('folio') or '')
    r.suc       = d.get('suc')
    r.fecha     = d.get('fecha')
    r.veredicto = d.get('veredicto')
    r.difs      = json.dumps(d.get('difs'))
    r.lectura   = json.dumps(d.get('lectura'))
    r.quien     = session.get('usuario')
    if not prev: db.session.add(r)
    db.session.commit()
    return jsonify(rev_dict(r))

@app.route('/api/revnotas/<int:rid>', methods=['DELETE'])
@requiere_login
def del_revnota(rid):
    r = RevNota.query.get(rid)
    if r:
        db.session.delete(r); db.session.commit()
    return jsonify({'ok': True})

with app.app_context():
    db.create_all()
    migrar_columnas()
    seed_usuarios()

if __name__ == '__main__':
    app.run(debug=True)
