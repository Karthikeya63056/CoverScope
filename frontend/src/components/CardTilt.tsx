import React, { useRef, useState } from 'react';
import { gsap } from 'gsap';

interface CardTiltProps {
  children: React.ReactNode;
  className?: string;
  maxTilt?: number;
  spotlight?: boolean;
  spotlightColor?: string;
  as?: React.ElementType;
  [key: string]: any;
}

export const CardTilt: React.FC<CardTiltProps> = ({
  children,
  className = '',
  maxTilt = 6,
  spotlight = true,
  spotlightColor = 'rgba(16, 185, 129, 0.15)',
  as: Component = 'div',
  ...rest
}) => {
  const cardRef = useRef<HTMLElement>(null);
  const [coords, setCoords] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setCoords({ x, y });

    const normX = x / rect.width - 0.5;
    const normY = y / rect.height - 0.5;

    if (
      window.matchMedia('(pointer: fine)').matches &&
      !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      gsap.to(cardRef.current, {
        y: -4,
        rotateY: normX * maxTilt,
        rotateX: -normY * maxTilt,
        transformPerspective: 1000,
        ease: 'power2.out',
        duration: 0.25,
      });
    }
  };

  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    if (!cardRef.current) return;
    gsap.to(cardRef.current, {
      y: 0,
      rotateX: 0,
      rotateY: 0,
      ease: 'power2.out',
      duration: 0.45,
    });
  };

  return (
    <Component
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`relative transform-gpu overflow-hidden ${className}`}
      style={{
        transformStyle: 'preserve-3d',
      }}
      {...rest}
    >
      {spotlight && isHovered && (
        <div
          className="pointer-events-none absolute -inset-px rounded-[inherit] transition-opacity duration-200 z-10"
          style={{
            background: `radial-gradient(320px circle at ${coords.x}px ${coords.y}px, ${spotlightColor}, transparent 75%)`,
          }}
          aria-hidden="true"
        />
      )}
      {children}
    </Component>
  );
};
