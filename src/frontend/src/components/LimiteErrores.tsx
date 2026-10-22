import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  /** Al cambiar este valor (p. ej. una nueva consulta) se vuelve a intentar pintar el contenido. */
  reiniciar?: unknown;
}

interface Estado {
  fallo: boolean;
}

/** Evita que un error de pintado deje la página en blanco (RF-U12): muestra un aviso y deja seguir. */
export class LimiteErrores extends Component<Props, Estado> {
  state: Estado = { fallo: false };

  static getDerivedStateFromError(): Estado {
    return { fallo: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Error al pintar la interfaz', error, info.componentStack);
  }

  componentDidUpdate(previas: Props) {
    if (this.state.fallo && previas.reiniciar !== this.props.reiniciar) this.setState({ fallo: false });
  }

  render() {
    if (this.state.fallo) {
      return (
        <div className="error" role="alert">
          Algo salió mal al mostrar la respuesta. Puedes seguir consultando o iniciar una nueva conversación.
        </div>
      );
    }
    return this.props.children;
  }
}
