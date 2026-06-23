from flask import Flask, jsonify, request, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import os, json

app = Flask(__name__, static_folder='estático')
app.secret_key = os.environ.get('CLAVE_SECRETA', 'impulso-secreto-2026')
db_url = os.environ.get('DATABASE_URL', 'sqlite:///impulso.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Pedido(db.Model):
    __tablename__ = 'pedido2'
    id          = db.Column(db.Integer, primary_key=True)
    folio       = db.Column(db.String(20), unique=True)
    cli         = db.Column(db.String(100))
    tel         = db.Column(db.String(20))
    suc         = db.Column(db.String(50))
    vendedor    = db.Column(db.String(50))
    fecha       = db.Column(db.String(20))
    mes         = db.Column(db.Integer)
    total       = db.Column(db.Float)
    hormiga     = db.Column(db.Float)
    descansar   = db.Column(db.Float)
    conoci      = db.Column(db.String(30))
    est         = db.Column(db.String(30))
    articulos   = db.Column(db.Text)

class Movimiento(db.Model):
    __tablename__ = 'movimiento2'
    id       = db.Column(db.Integer, primary_key=True)
    tipo     = db.Column(db.String(10))
    concepto = db.Column(db.String(100))
    monto    = db.Column(db.Float)
    fecha    = db.Column(db.String(20))
    mes      = db.Column(db.Integer)
    suc      = db.Column(db.String(50))
    notas    = db.Column(db.String(200))

USUARIOS = {
    'jardines': {'password': 'jardines123', 'suc': 'Jardines', 'rol': 'sucursal'},
    'zibata':   {'password': 'zibata123',   'suc': 'Zibata',   'rol': 'sucursal'},
    'admin':    {'password': 'admin123',    'suc': 'admin',    'rol': 'admin'},
}

def requiere_login(f):
    from functools import wraps
    @wraps(f)
    def decorado(*args, **kwargs):
        if not session.get('usuario'):
            return jsonify({'error': 'No autenticado'}), 401
        return f(*args, **kwargs)
    return decorado

@app.route('/')
def index():
    return send_from_directory('estático', 'index.html')

@app.route('/cotizador')
def cotizador():
    return send_from_directory('estático', 'Cotizador_Impulso.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    user = data.get('key', data.get('usuario', '')).strip()
    pwd  = data.get('pwd', data.get('password', '')).strip()
    u = USUARIOS.get(user)
    if u and u['password'] == pwd:
        session['usuario'] = user
        session['suc']     = u['suc']
        session['rol']     = u['rol']
        return jsonify({'ok': True, 'suc': u['suc'], 'rol': u['rol']})
    return jsonify({'ok': False, 'error': 'Credenciales incorrectas'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/me')
def me():
    u = session.get('usuario')
    if not u:
        return jsonify({'ok': False}), 401
    info = USUARIOS[u]
    return jsonify({'ok': True, 'usuario': u, 'suc': info['suc'], 'rol': info['rol']})

@app.route('/api/pedidos', methods=['GET'])
@requiere_login
def get_pedidos():
    suc = session.get('suc')
    rol = session.get('rol')
    q = Pedido.query
    if rol != 'admin':
        q = q.filter_by(suc=suc)
    return jsonify([p_dict(p) for p in q.order_by(Pedido.id.desc()).all()])

@app.route('/api/pedidos', methods=['POST'])
@requiere_login
def crear_pedido():
    data = request.json or {}
    p = Pedido(
        folio=data.get('folio'), cli=data.get('cli'), tel=data.get('tel'),
        suc=session.get('suc'), vendedor=data.get('vendedor'),
        fecha=data.get('fecha'), mes=data.get('mes'),
        total=data.get('total', 0), hormiga=data.get('hormiga', 0),
        descansar=data.get('descansar', 0), conoci=data.get('conoci'),
        est=data.get('est', 'Pendiente'),
        articulos=json.dumps(data.get('articulos', []))
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(p_dict(p)), 201

@app.route('/api/pedidos/<int:pid>', methods=['PUT'])
@requiere_login
def actualizar_pedido(pid):
    p = Pedido.query.get_or_404(pid)
    data = request.json or {}
    for campo in ['cli','tel','vendedor','fecha','mes','total','hormiga','descansar','conoci','est']:
        if campo in data:
            setattr(p, campo, data[campo])
    if 'articulos' in data:
        p.articulos = json.dumps(data['articulos'])
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
        'id': p.id, 'folio': p.folio, 'cli': p.cli, 'tel': p.tel,
        'suc': p.suc, 'vendedor': p.vendedor, 'fecha': p.fecha, 'mes': p.mes,
        'total': p.total, 'hormiga': p.hormiga, 'descansar': p.descansar,
        'conoci': p.conoci, 'est': p.est,
        'articulos': json.loads(p.articulos) if p.articulos else []
    }

@app.route('/api/movimientos', methods=['GET'])
@requiere_login
def get_movimientos():
    suc = session.get('suc')
    rol = session.get('rol')
    q = Movimiento.query
    if rol != 'admin':
        q = q.filter_by(suc=suc)
    return jsonify([m_dict(m) for m in q.order_by(Movimiento.id.desc()).all()])

@app.route('/api/movimientos', methods=['POST'])
@requiere_login
def crear_movimiento():
    data = request.json or {}
    m = Movimiento(
        tipo=data.get('tipo'), concepto=data.get('concepto'),
        monto=data.get('monto', 0), fecha=data.get('fecha'),
        mes=data.get('mes'), suc=session.get('suc'), notas=data.get('notas', '')
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
        'id': m.id, 'tipo': m.tipo, 'concepto': m.concepto,
        'monto': m.monto, 'fecha': m.fecha, 'mes': m.mes,
        'suc': m.suc, 'notas': m.notas
    }

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
