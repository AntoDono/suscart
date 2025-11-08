import { Vector3 } from "three";

export class Particle {
    originalPosition: Vector3;
    position: Vector3;
    velocity: Vector3;
    dampingFactor: number;
    maxDistanceTraveled: number;
    speed: number;
    direction: Vector3;
    
