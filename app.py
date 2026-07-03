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

USUARIOS = {
    'jardines': {'password':'jardines123','name':'Alondra','display':'Jardines','role':'venta','suc':'Jardines'},
    'zibata':   {'password':'zibata123',  'name':'Zibata', 'display':'Zibata',  'role':'venta','suc':'Zibata'},
    'admin':    {'password':'admin123',   'name':'Estefania','display':'Admin', 'role':'admin','suc':'Admin'},
}

def requiere_login(f):
    from functools import wraps
    @wraps(f)
    def decorado(*args, **kwargs):
        if not session.get('usuario'):
            return jsonify({'error': 'No autenticado'}), 401
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

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    key = data.get('key', '').strip()
    pwd = data.get('pwd', '').strip()
    u = USUARIOS.get(key)
    if u and u['password'] == pwd:
        session.permanent = True
        session['usuario'] = key
        session['suc'] = u['suc']
        session['rol'] = u['role']
        return jsonify({'ok': True, 'user': {
            'key': key, 'name': u['name'], 'display': u['display'],
            'role': u['role'], 'suc': u['suc'], 'pwd': pwd
        }})
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
    u = USUARIOS[key]
    return jsonify({'ok': True, 'user': {
        'key': key, 'name': u['name'], 'display': u['display'],
        'role': u['role'], 'suc': u['suc']
    }})

@app.route('/api/pedidos', methods=['GET'])
@requiere_login
def get_pedidos():
    rol = session.get('rol')
    suc = session.get('suc')
    q = Pedido.query
    if rol != 'admin':
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
        obs=d.get('obs'), est=d.get('est','Pendiente'), entrega=d.get('entrega')
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(p_dict(p)), 201

@app.route('/api/pedidos/<int:pid>', methods=['PUT'])
@requiere_login
def actualizar_pedido(pid):
    p = Pedido.query.get_or_404(pid)
    d = request.json or {}
    for campo in ['folio','tipo_venta','cli','tel','suc','vend','fecha','mes','sub','total','met','ant','rest','obs','est','entrega']:
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
        'est':p.est,'entrega':p.entrega
    }

@app.route('/api/movimientos', methods=['GET'])
@requiere_login
def get_movimientos():
    rol = session.get('rol')
    suc = session.get('suc')
    q = Movimiento.query
    if rol != 'admin':
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
    if rol != 'admin':
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

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
