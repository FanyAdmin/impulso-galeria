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

def emp_dict(e):
    return {'id':e.id,'nombre':e.nombre,'puesto':e.puesto,'suc':e.suc,
            'ingreso':e.ingreso,'salario':e.salario,'metpago':e.metpago,
            'banco':e.banco,'curp':e.curp,'rfc':e.rfc,'tel':e.tel,'dir':e.dir}

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
                 rfc=d.get('rfc',''), tel=d.get('tel',''), dir=d.get('dir',''))
    db.session.add(e)
    db.session.commit()
    return jsonify(emp_dict(e)), 201

@app.route('/api/empleados/<int:eid>', methods=['PUT'])
@requiere_admin
def actualizar_empleado(eid):
    e = Empleado.query.get_or_404(eid)
    d = request.json or {}
    for campo in ['nombre','puesto','suc','ingreso','salario','metpago','banco','curp','rfc','tel','dir']:
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
    rol = session.get('rol')
    suc = session.get('suc')
    q = Pedido.query
    if rol not in ('admin','owner','taller'):
        q = q.filter_by(suc=suc)
    return jsonify([p_dict(p) for p in q.order_by(Pedido.id.desc()).all()])

@app.route('/api/pedidos', methods=['POST'])
@requiere_login
def crear_pedido():
    d = request.json or {}
    p = Pedido(
        folio=d.get('folio'), tipo_venta=d.get('tipo_venta','general'),
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
    for campo in ['folio','tipo_venta','cli','tel','suc','vend','fecha','mes','sub','total','met','ant','rest','obs','est','entrega','taller_est','casillero']:
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
        'id':p.id,'folio':p.folio,'tipo_venta':p.tipo_venta,
        'cli':p.cli,'tel':p.tel,'suc':p.suc,'vend':p.vend,
        'fecha':p.fecha,'mes':p.mes,
        'items':json.loads(p.items) if p.items else [],
        'sub':p.sub,'total':p.total,'met':p.met,
        'ant':p.ant,'rest':p.rest,'obs':p.obs,
        'est':p.est,'entrega':p.entrega,
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

@app.route('/api/facturas', methods=['GET'])
@requiere_login
def get_facturas():
    return jsonify([])

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
                folio=d.get('folio'), tipo_venta=d.get('tipo_venta','general'),
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


# ── ÓRDENES DE COMPRA (lotes pedidos a proveedores) ───────────────────────────

class OrdenCompra(db.Model):
    __tablename__ = 'ordenes_compra'
    id          = db.Column(db.Integer, primary_key=True)
    prov        = db.Column(db.String(50))
    prov_nombre = db.Column(db.String(100))
    fecha       = db.Column(db.String(30))
    items       = db.Column(db.Text)  # JSON: [{mol,pzas,meds,fols}]

def ord_dict(o):
    return {'id':o.id,'prov':o.prov,'prov_nombre':o.prov_nombre,'fecha':o.fecha,
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
    return jsonify(ord_dict(o)), 201

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
    comision  = db.Column(db.Float, default=0)
    estatus   = db.Column(db.String(20), default='activo')

def vend_dict(v):
    return {'id':v.id,'nombre':v.nombre,'suc':v.suc,'comision':v.comision,'estatus':v.estatus}

@app.route('/api/vendedores', methods=['GET'])
@requiere_login
def get_vendedores():
    return jsonify([vend_dict(v) for v in Vendedor.query.order_by(Vendedor.nombre).all()])

@app.route('/api/vendedores', methods=['POST'])
@requiere_login
def crear_vendedor():
    d = request.json or {}
    v = Vendedor(nombre=d.get('nombre'), suc=d.get('suc',''), comision=d.get('comision',0), estatus=d.get('estatus','activo'))
    db.session.add(v)
    db.session.commit()
    return jsonify(vend_dict(v)), 201

@app.route('/api/vendedores/<int:vid>', methods=['PUT'])
@requiere_login
def actualizar_vendedor(vid):
    v = Vendedor.query.get_or_404(vid)
    d = request.json or {}
    for campo in ['nombre','suc','comision','estatus']:
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
    ]:
        try:
            db.session.execute(text(stmt)); db.session.commit()
        except Exception:
            db.session.rollback()
            try:  # SQLite local no soporta IF NOT EXISTS en columnas
                db.session.execute(text(stmt.replace(' IF NOT EXISTS',''))); db.session.commit()
            except Exception:
                db.session.rollback()

with app.app_context():
    db.create_all()
    migrar_columnas()
    seed_usuarios()

if __name__ == '__main__':
    app.run(debug=True)
