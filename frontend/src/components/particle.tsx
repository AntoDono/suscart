import { Vector3 } from "three";

export class Particle {
    originalPosition: Vector3;
    position: Vector3;
    velocity: Vector3;
    dampingFactor: number;
    maxDistanceTraveled: number;
    speed: number;
    direction: Vector3;

    constructor(position: Vector3) {
        this.originalPosition = position.clone();
        this.position = position.clone();
        this.velocity = new Vector3(0, 0, 0);
        this.dampingFactor = 0.95;
        this.maxDistanceTraveled = 1;
        this.speed = 0;
        this.direction = new Vector3(0, 0, 0);
    }
}
