/**
 * Orientación breve para respuestas «Sin información suficiente». La frase canónica del backend se muestra
 * intacta en la respuesta (lo exige el enunciado); esto solo sugiere qué preguntar.
 */
const SUGERENCIAS = [
  '¿Cuál es el plazo máximo del Crédito Agro Crece?',
  '¿Qué cubre Vida Protegida?',
  '¿Cuál es el tiempo objetivo de una PQR?',
];

export function Especialidades({ onSugerencia }: { onSugerencia: (pregunta: string) => void }) {
  return (
    <div className="especialidades" role="note" aria-label="Especialidades del asistente">
      <p>Puedo ayudarte con créditos, microseguros, procedimientos operativos y políticas internas. Prueba con:</p>
      <div className="ejemplos">
        {SUGERENCIAS.map((sugerencia) => (
          <button key={sugerencia} type="button" className="ejemplo" onClick={() => onSugerencia(sugerencia)}>
            {sugerencia}
          </button>
        ))}
      </div>
    </div>
  );
}
