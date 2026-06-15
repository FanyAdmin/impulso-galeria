from flask import Flask, jsonify, request, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os, json

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'impulso-secret-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///impulso.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ── MODELS ──
class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    folio = db.Column(db.String(20), unique=True)
    cli = db.Column(db.String(100))
    tel = db.Column(db.String(20))
    suc = db.Column(db.String(50))
    vend = db.Column(db.String(50))
    fecha = db.Column(db.String(20))
    mes = db.Column(db.Integer)
    total = db.Column(db.Float)
    ant = db.Column(db.Float)
    rest = db.Column(db.Float)
    met = db.Column(db.String(30))
    est = db.Column(db.String(30))
    entrega = db.Column(db.String(20))
    obs = db.Column(db.Text)
    tipo_venta = db.Column(db.String(20), default='general')
    factura_num = db.Column(db.String(30))
    items = db.Column(db.Text, default='[]')

class Movimiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20))
    concepto = db.Column(db.String(100))
    desc = db.Column(db.String(200))
    monto = db.Column(db.Float)
    fecha = db.Column(db.String(20))
    mes = db.Column(db.Integer)
    cuenta = db.Column(db.String(50))
    cta_destino = db.Column(db.String(50))
    socio = db.Column(db.String(50))

class Factura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    num = db.Column(db.String(30))
    rfc = db.Column(db.String(20))
    fecha = db.Column(db.String(20))
    folios = db.Column(db.Text)  # JSON array
    total = db.Column(db.Float)

class CuentaCobrar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    folio = db.Column(db.String(20))
    suc = db.Column(db.String(50))
    abonos = db.Column(db.Text, default='[]')

# ── AUTH ──
USERS = [
    {'key':'jardines','name':'Alondra','display':'Jardines','role':'venta','suc':'Jardines','pwd':'jardines123'},
    {'key':'zibata','name':'Yesica','display':'Zibata','role':'venta','suc':'Zibata','pwd':'zibata123'},
    {'key':'admin','name':'Estefania','display':'Admin','role':'admin','suc':'Admin','pwd':'admin123'}
]

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = next((u for u in USERS if u['key']==data.get('key') and u['pwd']==data.get('pwd')), None)
    if not user:
        return jsonify({'ok':False,'msg':'Credenciales incorrectas'}), 401
    session['user'] = user['key']
    return jsonify({'ok':True,'user':user})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok':True})

@app.route('/api/me')
def me():
    key = session.get('user')
    user = next((u for u in USERS if u['key']==key), None)
    if not user: return jsonify({'ok':False}), 401
    return jsonify({'ok':True,'user':user})

def current_user():
    key = session.get('user')
    return next((u for u in USERS if u['key']==key), None)

def require_login(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user():
            return jsonify({'ok':False,'msg':'No autenticado'}), 401
        return f(*args, **kwargs)
    return decorated

# ── PEDIDOS ──
@app.route('/api/pedidos')
@require_login
def get_pedidos():
    u = current_user()
    q = Pedido.query
    if u['role'] != 'admin':
        q = q.filter_by(suc=u['suc'])
    peds = q.order_by(Pedido.fecha.desc()).all()
    return jsonify([{
        'folio':p.folio,'cli':p.cli,'tel':p.tel,'suc':p.suc,'vend':p.vend,
        'fecha':p.fecha,'mes':p.mes,'total':p.total,'ant':p.ant,'rest':p.rest,
        'met':p.met,'est':p.est,'entrega':p.entrega,'obs':p.obs,
        'tipo_venta':p.tipo_venta,'factura_num':p.factura_num,
        'items':json.loads(p.items or '[]')
    } for p in peds])

@app.route('/api/pedidos', methods=['POST'])
@require_login
def create_pedido():
    d = request.json
    p = Pedido(**{k:v for k,v in d.items() if k != 'items'})
    p.items = json.dumps(d.get('items',[]))
    db.session.add(p)
    db.session.commit()
    return jsonify({'ok':True,'id':p.id})

@app.route('/api/pedidos/<folio>', methods=['PUT'])
@require_login
def update_pedido(folio):
    p = Pedido.query.filter_by(folio=folio).first_or_404()
    d = request.json
    for k,v in d.items():
        if k == 'items': p.items = json.dumps(v)
        elif hasattr(p, k): setattr(p, k, v)
    db.session.commit()
    return jsonify({'ok':True})

# ── MOVIMIENTOS ──
@app.route('/api/movimientos')
@require_login
def get_movimientos():
    movs = Movimiento.query.order_by(Movimiento.fecha.desc()).all()
    return jsonify([{
        'id':m.id,'tipo':m.tipo,'concepto':m.concepto,'desc':m.desc,
        'monto':m.monto,'fecha':m.fecha,'mes':m.mes,'cuenta':m.cuenta,
        'cta_destino':m.cta_destino,'socio':m.socio
    } for m in movs])

@app.route('/api/movimientos', methods=['POST'])
@require_login
def create_movimiento():
    d = request.json
    m = Movimiento(**d)
    db.session.add(m)
    db.session.commit()
    return jsonify({'ok':True,'id':m.id})

# ── FACTURAS ──
@app.route('/api/facturas')
@require_login
def get_facturas():
    facs = Factura.query.all()
    return jsonify([{
        'id':f.id,'num':f.num,'rfc':f.rfc,'fecha':f.fecha,
        'folios':json.loads(f.folios or '[]'),'total':f.total
    } for f in facs])

@app.route('/api/facturas', methods=['POST'])
@require_login
def create_factura():
    d = request.json
    f = Factura(num=d['num'],rfc=d['rfc'],fecha=d['fecha'],
                folios=json.dumps(d['folios']),total=d['total'])
    db.session.add(f)
    db.session.commit()
    return jsonify({'ok':True,'id':f.id})

@app.route('/api/facturas/<int:fid>', methods=['DELETE'])
@require_login
def delete_factura(fid):
    f = Factura.query.get_or_404(fid)
    db.session.delete(f)
    db.session.commit()
    return jsonify({'ok':True})

# ── SERVE APP ──
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('static', path)

# ── INIT DB ──
with app.app_context():
    db.create_all()
    # Load initial data if empty
    if Pedido.query.count() == 0:
        try:
            with open('seed_pedidos.json','r',encoding='utf-8') as f:
                peds = json.load(f)
            for p in peds:
                items = p.pop('items',[])
                ped = Pedido(**p)
                ped.items = json.dumps(items)
                db.session.add(ped)
            db.session.commit()
            print(f'Seeded {len(peds)} pedidos')
        except Exception as e:
            print(f'Seed error: {e}')
    if Movimiento.query.count() == 0:
        try:
            with open('seed_movimientos.json','r',encoding='utf-8') as f:
                movs = json.load(f)
            for m in movs:
                db.session.add(Movimiento(**m))
            db.session.commit()
            print(f'Seeded {len(movs)} movimientos')
        except Exception as e:
            print(f'Seed error: {e}')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)), debug=False)
