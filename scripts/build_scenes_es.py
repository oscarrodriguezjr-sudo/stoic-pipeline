# One-off helper that turned Script_10_Reglas_Estoicas_Para_Mantener_la_Calma.md
# into videos/reglas-estoicas-calma/scenes.json (CLAUDE.md Section 5 format).
# Not part of the runtime pipeline — kept for reference / re-editing.
import json
from pathlib import Path

IMG_SUFFIX = (
    " Cinematic painting, epic historical film still, ancient Rome, warm amber "
    "light against deep shadows, rich detail, no text, no letters, no watermark."
)

images = {
    "campamento-noche": "Roman legion winter camp on the Danube frontier at night, heavy rain, torches, a lone commander's tent" + IMG_SUFFIX,
    "tienda-lampara": "Interior of a Roman commander's tent at night, oil lamp light, a writing desk with scrolls" + IMG_SUFFIX,
    "epicteto-patio": "The Greek Stoic philosopher Epictetus, an older bearded man with a cane, teaching students in a sunlit stone courtyard" + IMG_SUFFIX,
    "epicteto-cerca": "Close-up portrait of the Stoic philosopher Epictetus, weathered face, calm expression, soft sunlight" + IMG_SUFFIX,
    "seneca-escribiendo": "The Roman philosopher Seneca writing by oil lamp at a wooden desk, night, warm candlelight" + IMG_SUFFIX,
    "vela-parpadeo": "Extreme close-up of a flickering oil lamp flame on a dark wooden desk, scrolls in soft focus behind it" + IMG_SUFFIX,
    "estatua-luz": "A Roman marble statue's face lit half in shadow, half in warm sunlight, dramatic contrast" + IMG_SUFFIX,
    "estatua-sombra": "A Roman marble statue in a quiet courtyard at dusk, long shadows, contemplative mood" + IMG_SUFFIX,
    "general-mapa": "A Roman general studying a battle map by lamplight in his tent before battle, armor in the background" + IMG_SUFFIX,
    "general-decidiendo": "A Roman general standing alone at the edge of a war camp at dawn, looking toward the horizon" + IMG_SUFFIX,
    "senado-tenso": "The Roman Senate chamber, crowded and tense, senators in togas arguing, dramatic lighting" + IMG_SUFFIX,
    "senado-discusion": "Close view of two Roman senators in heated argument, others watching, marble columns behind" + IMG_SUFFIX,
    "columna-amanecer": "A single Roman column standing alone in an empty field at dawn, mist, warm sunrise light" + IMG_SUFFIX,
    "campo-vacio": "A vast empty Roman field at sunrise, a single worn path leading toward distant ruins" + IMG_SUFFIX,
    "emperador-columnata": "A Roman emperor walking slowly through a stone colonnade, hands behind his back, calm posture" + IMG_SUFFIX,
    "emperador-caminando": "A Roman emperor in profile walking through a sunlit courtyard, deliberate and unhurried" + IMG_SUFFIX,
    "rio-roca": "A river flowing steadily around a large boulder in a forest, sunlight through trees" + IMG_SUFFIX,
    "puente-ingenieros": "Roman engineers building a wooden and stone bridge across a river, teamwork, daylight" + IMG_SUFFIX,
    "jardin-fuente": "A quiet Roman courtyard garden with a small stone fountain, evening light, peaceful" + IMG_SUFFIX,
    "jardin-atardecer": "A Roman villa garden at sunset, warm golden light, olive trees, empty stone bench" + IMG_SUFFIX,
    "desfile-triunfo": "A Roman triumph procession, a victorious general in a chariot, crowds cheering, banners" + IMG_SUFFIX,
    "sirviente-susurro": "Close view of a servant standing behind a triumphant Roman general's chariot, leaning in to whisper" + IMG_SUFFIX,
    "marco-amanecer": "Marcus Aurelius writing quietly in his tent at dawn, the rain has stopped, soft light through the tent flap" + IMG_SUFFIX,
}

def s(key, image, zoom, overlay, narration):
    return {"key": key, "image": image, "zoom": zoom, "overlay": overlay, "narration": narration}

scenes = [
    s("A", "campamento-noche", "in",
      {"type": "caption", "text": "FRONTERA DEL DANUBIO, AÑO 170"},
      "En el invierno del año 170, el Imperio Romano se estaba desmoronando. Una plaga había matado a millones. Las tribus germánicas habían cruzado el Danubio. El tesoro estaba tan vacío que el emperador subastó los muebles del palacio para pagarles a sus soldados."),
    s("B", "campamento-noche", "out",
      {"type": "capend", "text": "FRONTERA DEL DANUBIO, AÑO 170"},
      "Y por las noches, en una tienda fría en la frontera, ese emperador se sentaba a escribirse notas a sí mismo. No eran órdenes. No eran discursos. Eran recordatorios, sobre cómo mantener la calma cuando todo se derrumba. Se llamaba Marco Aurelio. Esas notas se convirtieron en Meditaciones."),
    s("C", "tienda-lampara", "out",
      {"type": "titlecard", "line1": "10 REGLAS ESTOICAS", "line2": "para mantener la calma"},
      "Hoy convertiremos sus palabras, y las de otros dos maestros estoicos, en diez reglas que puedes usar la próxima vez que sientas la presión. Ya sea una crisis en el trabajo, una conversación difícil, o una noche en la que tu mente no deja de dar vueltas."),

    s("1a", "epicteto-patio", "in",
      {"type": "title", "label": "REGLA 1", "text": "Sabe qué depende de ti"},
      "Epicteto nació esclavo. Según una antigua tradición, su amo le retorció la pierna hasta rompérsela. Más tarde se convirtió en uno de los maestros más respetados del mundo romano. Toda su filosofía comienza con una sola frase."),
    s("1q", "epicteto-patio", "in2",
      {"type": "quote", "lines": ["“Hay cosas que dependen de nosotros,", "y otras que no dependen de nosotros.”"], "author": "Epicteto"},
      "Hay cosas que dependen de nosotros, y otras que no dependen de nosotros."),
    s("1b", "epicteto-cerca", "out",
      {"type": "takeaway", "text": "Controla lo que puedas. Suelta lo que no."},
      "Tus juicios, tus decisiones, tu esfuerzo, tu manera de responder. Eso depende de ti. La economía, la opinión de los demás, el clima, el pasado. Eso no depende de ti. La presión aparece cuando mezclamos las dos cosas. Gastamos toda nuestra energía en lo que no podemos cambiar, y descuidamos lo que sí podemos. Así que cuando sientas la presión subir, traza una línea en medio de una hoja. A la izquierda: lo que controlo. A la derecha: lo que no controlo. Después, entrégate por completo al lado izquierdo, y suelta el lado derecho."),

    s("2a", "seneca-escribiendo", "in",
      {"type": "title", "label": "REGLA 2", "text": "Haz una pausa antes de reaccionar"},
      "Séneca asesoró a un emperador, administró una fortuna, y vio más política de la que la mayoría de nosotros verá jamás. Su consejo sobre la ira era simple."),
    s("2q", "seneca-escribiendo", "in2",
      {"type": "quote", "lines": ["“El mejor remedio", "contra la ira es esperar.”"], "author": "Séneca"},
      "El mejor remedio contra la ira es esperar."),
    s("2b", "vela-parpadeo", "out",
      {"type": "takeaway", "text": "Deja que tu juicio alcance a tus emociones."},
      "La primera reacción casi nunca es la más sabia. El correo que escribes en los primeros cinco minutos suele ser el que después lamentas. Un líder que hace una pausa no se ve débil. Se ve en control. Cuenta hasta diez. Respira lento, una sola vez. Di: déjame pensarlo. Y responde solo cuando tu juicio haya alcanzado a tus emociones."),

    s("3a", "estatua-luz", "in",
      {"type": "title", "label": "REGLA 3", "text": "Cuestiona tu primera versión de la historia"},
      "Un negocio se cae. Una persona dice: estoy acabado. Otra dice: ahora sé qué no funcionó. El mismo hecho. Dos noches de sueño completamente distintas."),
    s("3q", "estatua-luz", "in2",
      {"type": "quote", "lines": ["“No son las cosas las que perturban a los hombres,", "sino las opiniones que tienen de ellas.”"], "author": "Epicteto"},
      "No son las cosas las que perturban a los hombres, sino las opiniones que tienen de ellas."),
    s("3b", "estatua-sombra", "out",
      {"type": "takeaway", "text": "¿Qué pasó de verdad, y qué historia le agregué?"},
      "Marco Aurelio lo dijo así: cuando algo externo te perturba, el dolor no viene de lo que pasó, sino de tu estimación de lo que pasó, y esa estimación la puedes retirar en cualquier momento. La próxima vez que sientas subir la presión, pregúntate: ¿qué fue lo que realmente pasó? ¿Y qué historia le estoy agregando encima?"),

    s("4a", "general-mapa", "in",
      {"type": "title", "label": "REGLA 4", "text": "Ensaya lo peor con anticipación"},
      "Los estoicos tenían una práctica llamada premeditación de los males. Antes de un día difícil, imaginaban en silencio todo lo que podía salir mal."),
    s("4q", "general-mapa", "in2",
      {"type": "quote", "lines": ["“Sufrimos más en la imaginación", "que en la realidad.”"], "author": "Séneca"},
      "Sufrimos más en la imaginación que en la realidad."),
    s("4b", "general-decidiendo", "out",
      {"type": "takeaway", "text": "Prepárate para lo peor, y la realidad pierde su poder."},
      "No para preocuparse, sino para prepararse. Si el inversionista dice que no, ¿cuál es mi siguiente paso? Si el proyecto fracasa, ¿qué me queda? Cuando ya recorriste el peor escenario en tu mente, la realidad pierde su poder de sorprenderte. Ya estuviste ahí antes. Estás en calma porque estás preparado."),

    s("5a", "senado-tenso", "in",
      {"type": "title", "label": "REGLA 5", "text": "Espera a las personas difíciles"},
      "Cada mañana, Marco Aurelio se preparaba con un recordatorio. Hoy, se decía a sí mismo, me voy a encontrar con personas entrometidas, desagradecidas, arrogantes y deshonestas."),
    s("5b", "senado-discusion", "out",
      {"type": "takeaway", "text": "Cuando dejan de sorprenderte, dejan de controlarte."},
      "Suena cínico. No lo es. Es una armadura. Cuando esperas a las personas difíciles, dejan de sorprenderte. Y cuando dejan de sorprenderte, dejan de controlarte. Puedes tratarlas con calma, incluso con amabilidad, porque ya las viste venir."),

    s("6a", "columna-amanecer", "in",
      {"type": "title", "label": "REGLA 6", "text": "Haz menos, pero haz lo que importa"},
      "Marco escribió que si quieres paz mental, hagas menos cosas, y te preguntes de cada una: ¿es esto necesario?"),
    s("6b", "campo-vacio", "out",
      {"type": "takeaway", "text": "Haz bien una o dos cosas, y deja que el resto espere."},
      "La mayor parte de la presión no la causa un solo problema grande. La causan cincuenta pequeños peleando por tu atención. Así que bajo presión, simplifica. ¿Cuáles son las una o dos cosas que de verdad importan hoy? Haz esas bien, y deja que el resto espere."),

    s("7a", "emperador-columnata", "in",
      {"type": "title", "label": "REGLA 7", "text": "Domina tu cuerpo primero"},
      "Marco admiraba a su padre adoptivo, el emperador Antonino Pío, casi más que a nadie. ¿Qué lo distinguía? Su calma. Nunca actuaba con prisa, nunca con dureza, nunca se alteraba, ni siquiera bajo el peso de un imperio."),
    s("7b", "emperador-caminando", "out",
      {"type": "takeaway", "text": "Tu mente sigue a tu cuerpo."},
      "La calma no es solo un pensamiento. Es una postura. Baja la voz. Habla más despacio. Exhala más tiempo del que inhalas. Tu mente sigue a tu cuerpo. Y las personas a tu alrededor siguen tu calma."),

    s("8a", "rio-roca", "in",
      {"type": "title", "label": "REGLA 8", "text": "Usa el obstáculo"},
      "Cuando un plan se rompe, el estoico no pregunta por qué a mí. Pregunta: ¿qué hace esto posible?"),
    s("8q", "rio-roca", "in2",
      {"type": "quote", "lines": ["“Lo que se interpone en el camino", "se convierte en el camino.”"], "author": "Marco Aurelio"},
      "El obstáculo para la acción hace avanzar la acción. Lo que se interpone en el camino se convierte en el camino."),
    s("8b", "puente-ingenieros", "out",
      {"type": "takeaway", "text": "El obstáculo no bloquea tu camino. Es tu camino."},
      "Un cliente perdido te enseña qué le falta a tu oferta. Un tropiezo te obliga a volverte más creativo, más paciente, más resistente. El obstáculo no bloquea tu camino. Es tu camino. [Espacio para historia personal: un momento real de tu carrera en el que un tropiezo se convirtió en ventaja.]"),

    s("9a", "jardin-fuente", "in",
      {"type": "title", "label": "REGLA 9", "text": "Construye tu ciudadela interior"},
      "Los romanos adinerados escapaban a villas junto al mar o en las montañas. Marco decía que tú no lo necesitas."),
    s("9q", "jardin-fuente", "in2",
      {"type": "quote", "lines": ["“En ningún lugar encuentra el hombre un retiro más tranquilo", "que en su propia alma.”"], "author": "Marco Aurelio"},
      "En ningún lugar encuentra el hombre un retiro más tranquilo o más libre de perturbaciones que en su propia alma."),
    s("9b", "jardin-atardecer", "out",
      {"type": "takeaway", "text": "Siempre puedes construir un lugar tranquilo dentro de la tormenta."},
      "Cinco minutos de silencio antes de una reunión. Una caminata corta sin tu teléfono. Unas líneas en un diario por la noche, tal como lo hacía Marco. No siempre puedes salir de la tormenta. Pero siempre puedes construir un lugar tranquilo dentro de ella."),

    s("10a", "desfile-triunfo", "in",
      {"type": "title", "label": "REGLA 10", "text": "Memento mori"},
      "Se dice que en la antigua Roma, durante un desfile de victoria, un esclavo se paraba detrás del general triunfante, susurrándole: recuerda, solo eres un hombre."),
    s("10b", "sirviente-susurro", "out",
      {"type": "takeaway", "text": "Recuerda lo corta que es la vida, y la presión vuelve a su tamaño real."},
      "Marco se recordaba a sí mismo que podía dejar esta vida en cualquier momento, y dejaba que eso diera forma a lo que hacía, decía y pensaba. Esto no es morboso. Es clarificador. El correo que se siente como una crisis, la discusión que parece tan importante. ¿Importará algo de esto en un año? ¿En diez? Cuando recuerdas lo corta que es la vida, la mayoría de la presión vuelve a su tamaño real."),

    s("Z1", "marco-amanecer", "out",
      {"type": "center", "lines": ["No puedes controlar la tormenta.", "Puedes controlarte a ti mismo."]},
      "Marco Aurelio nunca tuvo un mundo en calma. Tuvo plaga, guerra y traición. Lo que construyó fue una mente en calma. ¿Cuál de estas diez reglas vas a practicar esta semana? Cuéntamelo en los comentarios. Leo todos."),
    s("Z2", "marco-amanecer", "out",
      {"type": "sub", "text": "SUSCRÍBETE", "channel_name": "Estoicismo Para Líderes"},
      "Y si quieres más sabiduría antigua para líderes modernos, suscríbete a Estoicismo Para Líderes."),
]

doc = {
    "title": "10 Reglas Estoicas Para Mantener la Calma",
    "channel": "es",
    "scenes": scenes,
    "images": images,
}

out = Path(__file__).resolve().parent.parent / "videos" / "reglas-estoicas-calma" / "scenes.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"wrote {out} ({len(scenes)} scenes, {len(images)} unique images)")
