import type { Fuente } from '../api';

export function Fuentes({ fuentes }: { fuentes: Fuente[] }) {
  if (fuentes.length === 0) {
    return <p className="sin-fuentes">Sin fuentes: la respuesta no se basa en ningún documento.</p>;
  }
  return (
    <section className="fuentes" aria-label="Fuentes utilizadas">
      <h3>Fuentes</h3>
      <ol>
        {fuentes.map((fuente) => (
          <li key={`${fuente.archivo}-${fuente.seccion}`}>
            <span className="fuente-archivo">{fuente.archivo}</span>
            <span className="fuente-seccion"> › {fuente.seccion}</span>
            {fuente.extracto && <blockquote>{fuente.extracto}</blockquote>}
          </li>
        ))}
      </ol>
    </section>
  );
}
