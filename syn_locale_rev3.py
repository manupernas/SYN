"""Fallbacks for old hard-coded SYN UI strings, not IPTV provider content."""
import re

EN = {
 'Calendario, programación y grabaciones': 'Schedules, programmes and recordings',
 'SYN DVR está grabando en segundo plano': 'SYN DVR is recording in the background',
 'Regresar al último canal en directo': 'Return to the last live channel',
 'Grabar canal actual': 'Record the current channel',
 'DVR · Grabaciones': 'DVR · Recordings',
 'Abrir carpeta de grabaciones': 'Open recordings folder',
 'Elegir carpeta…': 'Choose folder…',
 'Cambiar la carpeta donde se guardan las grabaciones': 'Change the recordings folder',
 'Programar una grabación': 'Schedule a recording',
 'Fecha': 'Date', 'Canal': 'Channel', 'Horario (24 h)': 'Time (24-hour)',
 'Cargando canales…': 'Loading channels…',
 'Inicio: HH:MM': 'Start: HH:MM', 'Fin: HH:MM': 'End: HH:MM',
 'De': 'From', 'a': 'to',
 'Programar grabación': 'Schedule recording',
 '● Grabar canal seleccionado ahora': '● Record selected channel now',
 'Se utiliza FFmpeg sin recodificar y User-Agent VLC.': 'FFmpeg records without transcoding using the VLC User-Agent.',
 'Programadas y grabadas': 'Scheduled and recorded',
 'Actualizar grabaciones': 'Refresh recordings',
 'Servicio DVR: comprobando…': 'DVR service: checking…',
 'La grabación ya no está disponible.': 'The recording is no longer available.',
 'La carpeta de grabaciones todavía no existe.': 'The recordings folder does not exist yet.',
 '● DVR programado: ': '● DVR scheduled: ',
 '● Programar grabación': '● Schedule recording',
 'Grabación inmediata solicitada: ': 'Instant recording requested: ',
 'Grabación programada: ': 'Recording scheduled: ',
 'Grabar ahora': 'Record now', 'Detener grabación': 'Stop recording',
 'DVR: deteniendo grabación…': 'DVR: stopping recording…',
 'DVR: reproduce un canal antes de grabar.': 'DVR: play a channel before recording.',
 'DVR: grabación solicitada de ': 'DVR: recording requested for ',
 'El archivo ya no está disponible: ': 'The file is no longer available: ',
 'Carpeta: ': 'Folder: ',
 'Programada': 'Scheduled', 'Grabando': 'Recording',
 'Finalizada': 'Completed', 'Cancelada': 'Cancelled',
 'Perdida': 'Missed', 'Interrumpida': 'Interrupted',
 'Detener': 'Stop', 'Cancelar': 'Cancel', '▶ Ver': '▶ Play',
 'Abrir ubicación del archivo original': 'Open original file location',
 'Todavía no hay grabaciones.': 'No recordings yet.',
 'DVR: viendo la señal compartida, sin segunda conexión IPTV': 'DVR: viewing the shared stream without a second IPTV connection',
 'DVR: esperando al grabador o su reconexión…': 'DVR: waiting for the recorder or reconnection…',
 'DVR: viendo la señal compartida': 'DVR: viewing the shared stream',
 'DVR: esperando la señal compartida…': 'DVR: waiting for the shared stream…',
 'DVR compartido: ': 'Shared DVR: ',
 'Grabación terminada: ': 'Recording finished: ',
 '● Grabación en curso: ': '● Recording in progress: ',
 ' · continuará al cerrar la ventana de SYN.': ' · continues after closing SYN.',
 'User-Agent de reproducción (MPV)': 'Playback User-Agent (MPV)',
 'User-Agent personalizado de reproducción': 'Custom playback User-Agent',
 'No se pudo iniciar el vídeo\n\n': 'Could not start the video\n\n',
 'No hay favoritos todavía. Marca ♡ en algún canal.': 'No favourites yet. Mark ♡ on a channel.',
 'No hay canales que coincidan con este filtro.': 'No channels match this filter.',
 'Favoritos': 'Favourites',
 'Servicio DVR: activo': 'DVR service: active',
 'Servicio DVR: no disponible': 'DVR service: unavailable',
 'Abrir SYN': 'Open SYN',
 '● Grabando: ': '● Recording: ',
 'canal': 'channel', 'canales': 'channels',
 'grabación': 'recording', 'grabaciones': 'recordings',
 'Grabaciones': 'Recordings',
 '  Y ': '  And ', ' grabaciones más': ' more recordings',
 ' en segundo plano': ' in the background',
 'Propiedad no disponible': 'Property unavailable',
}
# SYN 1.3.6beta11: fallbacks for current UI text absent from older .mo files.
# en_US/en_GB grammatical variants are handled by localize() below.
EN.update({
 'Sistema, Claro, Oscuro, Teal SYN, Nord claro/oscuro y Gruvbox claro/oscuro. Acentos Frost, Aurora y Gruvbox en Apariencia.':
    'System, Light, Dark, SYN Teal, Nord Light/Dark and Gruvbox Light/Dark. Frost, Aurora and Gruvbox accents in Appearance.',
 'Buscar títulos…': 'Search titles…',
 '¿Qué te apetece ver?': 'What would you like to watch?',
 'Selecciona una categoría para explorar tu contenido': 'Select a category to explore your content',
 'Ver más títulos': 'Show more titles',
 'No se pudo consultar el catálogo del servidor. Revisa tu fuente Xtream.':
    'Could not load the server catalogue. Check your Xtream source.',
 'de': 'of',
 '● Programar grabación': '● Schedule recording',
 'Conexiones máximas del perfil': 'Maximum connections for this profile',
 'Timeshift: no disponible durante una grabación de este canal.':
    'Timeshift: unavailable while recording this channel.',
 'Timeshift: todas las conexiones están ocupadas por el DVR.':
    'Timeshift: all connections are in use by the DVR.',
 'Timeshift: preparando búfer temporal…': 'Timeshift: preparing temporary buffer…',
 'Timeshift: sin señal inicial; regreso al directo.':
    'Timeshift: no initial signal; returning to live TV.',
 'Timeshift: límite de almacenamiento; regresando al directo.':
    'Timeshift: storage limit reached; returning to live TV.',
 'Cast: relay compartido no disponible; no se abrirá una conexión duplicada.':
    'Cast: shared relay unavailable; no duplicate connection will be opened.',
 'Cast: recuperando canal compartido sin otra conexión IPTV…':
    'Cast: restoring the shared channel without another IPTV connection…',
 'Cast: libmpv no está listo para abrir el relay local.':
    'Cast: libmpv is not ready to open the local relay.',
 'Cast: mismo canal en SYN y Chromecast · una conexión IPTV':
    'Cast: same channel in SYN and Chromecast · one IPTV connection',
 'Cast finalizado; DVR y reproducción local protegidos.':
    'Cast ended; DVR and local playback are protected.',
 'Cast: espera a que termine la operación anterior.':
    'Cast: wait for the previous operation to finish.',
 'Cast: todas las conexiones están ocupadas por el DVR.':
    'Cast: all connections are in use by the DVR.',
 'Cast: preparando retransmisión compartida…':
    'Cast: preparing shared stream…',
 'Cast: puente antiguo, falta el relay local. Detén Cast.':
    'Cast: outdated bridge; local relay is missing. Stop casting.',
 'Cast: operación en curso.': 'Cast: operation in progress.',
 'Detén Cast antes de cambiar de perfil IPTV.':
    'Stop casting before switching IPTV profiles.',
 'DVR: conexiones ocupadas. Selecciona uno de los canales que se están grabando.':
    'DVR: connections in use. Select one of the channels being recorded.',
 'DVR: límite de conexiones alcanzado.': 'DVR: connection limit reached.',
})

ES = {
 'channels': 'canales', 'categories': 'categorías', 'channels loaded': 'canales cargados',
 'profile': 'perfil', 'Loading profile': 'Cargando perfil', 'of': 'de',
 'Showing': 'Mostrando', 'search to filter': 'busca para filtrar',
 'Page': 'Página', 'Next 24': 'Siguientes 24', 'page': 'página',
 'scroll for more': 'desplázate para ver más', 'to': 'a',
}

def localize(message, translated, language):
    if language == 'es':
        return ES.get(message, translated)
    if language not in ('en_US', 'en_GB'):
        return translated
    output = translated if translated != message else EN.get(message, translated)
    if language == 'en_US':
        swaps = {'favourites':'favorites','favourite':'favorite', 'Favourites':'Favorites',
                 'Favourite':'Favorite','colour':'color','colours':'colors',
                 'Colour':'Color','Colours':'Colors','programme':'program',
                 'programmes':'programs','Programmes':'Programs','customise':'customize',
                 'Customise':'Customize','organise':'organize'}
    else:
        swaps = {'favorites':'favourites','favorite':'favourite','Favorites':'Favourites',
                 'Favorite':'Favourite','color':'colour','colors':'colours',
                 'Color':'Colour','Colors':'Colours','program':'programme',
                 'programs':'programmes','Programs':'Programmes','customize':'customise'}
    for old,new in swaps.items():
        output = re.sub(r'\b'+re.escape(old)+r'\b',new,output)
    return output
