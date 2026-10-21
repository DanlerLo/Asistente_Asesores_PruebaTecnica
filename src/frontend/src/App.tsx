import { useCallback, useEffect, useState } from 'react';
import { consultar, ErrorApi, obtenerHistorial, type RegistroHistorial, type RespuestaConsulta } from './api';
import { FormularioConsulta } from './components/FormularioConsulta';
import { Historial } from './components/Historial';
import { Respuesta } from './components/Respuesta';

export const MAX_LONGITUD_PREGUNTA = 1000;

export default function App() {
  const [procesando, setProcesando] = useState(false);
  const [resultado, setResultado] = useState<RespuestaConsulta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [historial, setHistorial] = useState<RegistroHistorial[]>([]);

  const cargarHistorial = useCallback(async () => {
    try {
      setHistorial(await obtenerHistorial(10));
    } catch {
      // El historial es informativo: si falla no interrumpe la consulta.
    }
  }, []);

  useEffect(() => {
    void cargarHistorial();
  }, [cargarHistorial]);

  async function enviar(pregunta: string) {
    const limpia = pregunta.trim();
    if (!limpia) {
      setError('Escribe una pregunta antes de consultar.');
      return;
    }
    if (limpia.length > MAX_LONGITUD_PREGUNTA) {
      setError(`La pregunta supera el máximo de ${MAX_LONGITUD_PREGUNTA} caracteres.`);
      return;
    }
    setProcesando(true);
    setError(null);
    setResultado(null);
    try {
      setResultado(await consultar(limpia));
      void cargarHistorial();
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : 'Ocurrió un error inesperado. Intenta de nuevo.');
    } finally {
      setProcesando(false);
    }
  }

  return (
    <main className="app">
      <header className="cabecera">
        <h1>Asistente para asesores comerciales</h1>
        <p>Responde con la documentación oficial de productos, microseguros, procedimientos y políticas.</p>
      </header>

      <FormularioConsulta procesando={procesando} onEnviar={enviar} />

      {procesando && (
        <p className="estado-proceso" role="status" aria-live="polite">
          Procesando la consulta…
        </p>
      )}

      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}

      {resultado && <Respuesta resultado={resultado} />}

      <Historial registros={historial} onSeleccionar={enviar} />
    </main>
  );
}
