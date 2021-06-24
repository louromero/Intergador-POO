from datetime import datetime
import hashlib
from flask import Flask, request, render_template, url_for
from werkzeug.utils import redirect

app = Flask(__name__)
app.config.from_pyfile('config.py')

from models import db
from models import Usuario, Movil, Viaje


#-------------------------------------INICIO------------------------------------------------------
@app.route('/inicio')
def inicio():
    return render_template('index.html')

#-------------------------------------INICIAR SESION----------------------------------------------
@app.route('/iniciar_sesion')
def iniciar_sesion():
    return render_template('iniciar_sesion.html', iniciarSesion=True)

#Verificar datos de los usuarios
@app.route('/autenticar_usuario', methods=['GET','POST'])
def autenticar_usuario():
    if request.method == 'POST':
        usuario_actual =  Usuario.query.filter_by(dni=request.form['usuario']).first()
        if usuario_actual is None:
            return render_template('iniciar_sesion.html', iniciarSesion=True, usuario = False)
        else:
            #verifico contraseña
            clave = request.form['password']
            clave_cifrada = hashlib.md5(bytes(clave, encoding='utf-8'))
            if clave_cifrada.hexdigest() == usuario_actual.clave:
                #Envio como dato el usuario para saber que funcionalidades tiene y tipo
                if usuario_actual.tipo == 'cli':
                    return redirect(url_for('cliente',cliente_dni = usuario_actual.dni))
                elif usuario_actual.tipo == 'op':
                    return redirect(url_for('operador',operador_dni = usuario_actual.dni))
            else:
                return render_template('iniciar_sesion.html',iniciarSesion=True, password = False)

#Se registran los usuarios
@app.route('/formulario_registrar_usuario')
def formulario_registrar_usuario():
    return render_template('iniciar_sesion.html',registrarUsuario=True)

@app.route('/registrar_usuario', methods=['GET','POST'])
def registrar_usuario():
    if request.method == 'POST':
        #chequear si el usuario ya esta registrado o no y mostrar el mensaje
        usuario =  Usuario.query.filter_by(dni=request.form['dni']).first()
        if usuario == None:
            #Cifro contraseña antes de crear el usuario:
            clave = request.form['password']
            clave_cifrada = hashlib.md5(bytes(clave, encoding='utf-8'))
            #Agrego el nuevo usuario por defecto de tipo cliente
            nuevo_usuario = Usuario(
                dni = request.form['dni'],
                nombre = request.form['nombre'],
                clave = clave_cifrada.hexdigest(),
                tipo = 'cli'
            )
            db.session.add(nuevo_usuario)
            db.session.commit()
            #Mostrar el mensaje en la planilla
            return render_template('iniciar_sesion.html', registrarUsuario=True, exito=True)
        else:
            return render_template('iniciar_sesion.html', registrarUsuario=True, usuarioRegistrado=True)


#-------------------------------------CLIENTE----------------------------------------------------------------

@app.route('/cliente/<int:cliente_dni>', methods=['GET','POST'])
@app.route('/cliente/<int:cliente_dni>/<int:estado>', methods=['GET','POST'])
def cliente(cliente_dni,estado = False):
    usuario_actual =  Usuario.query.filter_by(dni=cliente_dni).first()
    [viajes_usuario_actual, moviles_actual] = cargar_viajes_usuario(cliente_dni)    
    return render_template('cliente.html', 
                            datos=usuario_actual, 
                            viajes = viajes_usuario_actual, 
                            moviles = moviles_actual, 
                            estado = estado)

#Solicita un viaje
@app.route('/solicitar_viaje/<int:cliente_dni>', methods=['GET','POST'])
def solicitar_viaje(cliente_dni):
    if request.method == 'POST':

        equipaje = request.form['equipaje']
        if equipaje == 'on':
            equipaje = 1
        else:
            equipaje = 0
        
        nuevo_viaje = Viaje(
                            origen = request.form['dirOrigen'],
                            destino = request.form['dirDestino'],
                            fecha = datetime.today(),
                            importe = 0.0,
                            pasajeros = request.form['cantPasajeros'],
                            equipaje = equipaje,
                            dniCliente = cliente_dni 
                        )
        print(request.form['equipaje'])
        #Guardar en la base de datos
        db.session.add(nuevo_viaje)
        db.session.commit()
        #Envio estado verdadero para indicar que se muestre el modal de movil solicitado
        return redirect(url_for('cliente',cliente_dni=cliente_dni,estado = True))


#Carga viajes del usuario
def cargar_viajes_usuario(dni):
    #Leo viajes que aun no finalizan
    viajes = Viaje.query.filter_by(duracion=None).all()
    #Almaceno solo los del usuario
    viajes_pasajero = []
    for viaje in viajes:
        if str(viaje.dniCliente) == str(dni):
            viajes_pasajero.append(viaje)
    moviles = []
    for viaje in viajes_pasajero:
        movil = Movil.query.filter_by(numero = viaje.numMovil).first()
        if movil not in moviles:
            moviles.append(movil)   
    return [viajes_pasajero, moviles]


#------------------------------------------------OPERADOR----------------------------------------------------------------
@app.route('/operador/<int:operador_dni>')
@app.route('/operador/<int:operador_dni>/<int:estado>')
@app.route('/operador/<int:operador_dni>/<int:estado>/<int:numero>/<fecha>')
def operador(operador_dni,estado=False,numero=None,fecha=None):
    operador_actual= Usuario.query.filter_by(dni=operador_dni).first()
    viajes_duracion=Viaje.query.filter_by(duracion=None).all()
    viajes_sin_movil=Viaje.query.filter_by(numMovil=None).all()
    viajes_sin_finalizar=[]
    for viaje in viajes_duracion:
        if viaje.numMovil!=None:
            viajes_sin_finalizar.append(viaje)

    moviles=Movil.query.all()
    viajes_realizados=[]
    importe=0

    #Se cargan los viajes que ya fueron viajes_realizados
    if estado==True:
        viajes=Viaje.query.filter_by(numMovil=numero).all()
        #Convierto la fecha en string
        for viaje in viajes:
            fecha_viaje=viaje.fecha.strftime("%Y-%m-%d")
            if fecha_viaje==fecha and viaje.duracion!=None:
                viajes_realizados.append(viaje)
                importe+=viaje.importe

    return render_template('operador.html',
                            datos=operador_actual,
                            viajes_realizados= viajes_realizados,
                            viajes_sin_movil=viajes_sin_movil,
                            viajes_sin_finalizar=viajes_sin_finalizar,
                            moviles=moviles,
                            estado = estado,
                            fechaM=fecha,
                            numero_movil=numero,
                            importe=importe)


#Se realiza la finalizacion del viaje
@app.route('/finalizar_viaje/<int:operador_dni>/<int:id_viaje>',methods=['GET','POST'])
def finalizar_viaje(operador_dni,id_viaje):
    if request.method == 'POST':
        viaje= Viaje.query.filter_by(idViaje=id_viaje).first()
        duracion= request.form['duracion']
        #Calcula el importe
        imp= importe_total(duracion,viaje.demora)
        viaje.importe= imp
        viaje.duracion=duracion
        #Guardar cambios
        db.session.commit()
        return redirect(url_for('operador',operador_dni=operador_dni,estado=0))



#Se calcula el importe
def importe_total(duracion,demora):
    importe_variable= int(duracion)* 5
    importe_viaje= 100 + importe_variable
    if demora > 15:
        #Se calcula el descuento
        importe_viaje -= importe_viaje * 0.10
    #Redondea un número a solo dos decimales
    return round(importe_viaje,2)

#Consultar viajes
@app.route('/consultar_viajes/<int:operador_dni>',methods=['GET','POST'])
def consultar_viajes(operador_dni):
    if request.method == 'POST':
        numero=request.form['numMovil']
        fecha=request.form['fecha']
    return redirect(url_for('operador',
                            operador_dni=operador_dni,
                            estado=True,
                            numero=numero,
                            fecha=fecha))

#Lo que hace es hacer que se vuelva a ver la pestaña para consultar otro viaje
@app.route('/volver/<int:operador_dni>', methods=['GET','POST'])
def volver(operador_dni):
    return redirect(url_for('operador',
                            operador_dni = operador_dni,
                            estado = False))

#Se le asigna el movil a las solicitudes de viajes
@app.route('/asignar_movil/<int:operador_dni>/<int:id_viaje>',methods=['GET','POST'])
def asignar_movil(operador_dni,id_viaje):
    if request.method == 'POST':
        viaje= Viaje.query.filter_by(idViaje=id_viaje).first()
        viaje.numMovil= request.form['numMovil']
        viaje.demora= request.form['demora']
        #Guarda los cambios
        db.session.commit()
        return redirect(url_for('operador',operador_dni=operador_dni))

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)