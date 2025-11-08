import './SimpleGlass.css';
import { ReactNode, CSSProperties } from 'react';

interface SimpleGlassProps {
  children?: ReactNode;
  width?: number | string;
  height?: number | string;
  borderRadius?: number;
  style?: CSSProperties;
}

export default function SimpleGlass({
  children,
  width = 350,
  height = 500,
  borderRadius = 0,
  style = {}
}: SimpleGlassProps) {
  const containerStyle: CSSProperties = {
    ...style,
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
    borderRadius: `${borderRadius}px`,
  };

  return (
    <div className="simple-glass" style={containerStyle}>
      <div className="simple-glass-content">{children}</div>
    </div>
  );
}
