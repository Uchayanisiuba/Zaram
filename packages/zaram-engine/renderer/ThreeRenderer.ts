import * as THREE from 'three';
import { AssetDescriptor } from '../types/AssetDescriptor';
import { MaterialDescriptor } from '../types/MaterialDescriptor';
import { ShaderDescriptor } from '../types/ShaderDescriptor';
import { LODDescriptor, LODLevel } from '../types/LODDescriptor';
import { FrameState } from '../types/FrameState';
import { PerformanceOverlay } from './PerformanceOverlay';

export interface RenderPayload {
  asset: AssetDescriptor;
  material: MaterialDescriptor;
  shader: ShaderDescriptor;
  lod?: {
    assetId: string;
    materialOverrides?: Partial<MaterialDescriptor>;
  };
  frameState: FrameState;
  transform?: {
    position: [number, number, number];
    rotation: [number, number, number];
    scale: [number, number, number];
  };
}

export interface RenderContext {
  canvas: HTMLCanvasElement;
  width: number;
  height: number;
}

interface ThreeRenderObject {
  mesh: THREE.Mesh;
  assetId: string;
  materialId: string;
  shaderId: string;
  lodLevel: number;
}

const getDevicePixelRatio = (): number => {
  if (typeof window !== 'undefined' && window.devicePixelRatio) {
    return window.devicePixelRatio;
  }
  return 1;
};

export class ThreeRenderer {
  private ctx: RenderContext | null = null;
  private renderer: THREE.WebGLRenderer | null = null;
  private scene: THREE.Scene | null = null;
  private camera: THREE.PerspectiveCamera | null = null;
  private readonly overlay = new PerformanceOverlay();
  private renderObjects: Map<string, ThreeRenderObject> = new Map();
  private geometryCache: Map<string, THREE.BufferGeometry> = new Map();
  private materialCache: Map<string, THREE.Material> = new Map();
  private shaderCache: Map<string, THREE.ShaderMaterial> = new Map();
  private lodCache: Map<string, LODDescriptor> = new Map();
  private frameId = 0;
  private lastStatsTime = 0;
  private stats: ReturnType<PerformanceOverlay['getStats']> | null = null;
  private isInitialized = false;
  private animationFrameId: number | null = null;

  initialize(ctx: RenderContext): void {
    if (this.isInitialized) return;

    this.ctx = ctx;

    this.renderer = new THREE.WebGLRenderer({
      canvas: ctx.canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    this.renderer.setSize(ctx.width, ctx.height);
    this.renderer.setPixelRatio(getDevicePixelRatio());
    this.renderer.shadowMap.enabled = false;
    this.renderer.autoClear = true;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x000000);

    this.camera = new THREE.PerspectiveCamera(60, ctx.width / ctx.height, 0.1, 1000);
    this.camera.position.set(0, 0, 50);

    const ambientLight = new THREE.AmbientLight(0x404040, 1);
    this.scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
    directionalLight.position.set(10, 20, 10);
    this.scene.add(directionalLight);

    this.isInitialized = true;
  }

  resize(width: number, height: number): void {
    if (!this.renderer || !this.camera || !this.ctx) return;
    this.ctx.width = width;
    this.ctx.height = height;
    this.renderer.setSize(width, height);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  setCamera(position: [number, number, number], target: [number, number, number] = [0, 0, 0]): void {
    if (!this.camera) return;
    this.camera.position.set(position[0], position[1], position[2]);
    this.camera.lookAt(target[0], target[1], target[2]);
  }

  render(payloads: RenderPayload[], frameState: FrameState): void {
    if (!this.ctx || !this.renderer || !this.scene || !this.camera) return;

    const t0 = performance.now();
    let triangleCount = 0;
    let drawCalls = 0;

    const visibleIds = new Set<string>();

    for (const payload of payloads) {
      const obj = this.getOrCreateRenderObject(payload);
      if (obj) {
        visibleIds.add(obj.assetId);
        triangleCount += obj.mesh.geometry.attributes.position?.count || 0;
        drawCalls++;
      }
    }

    for (const [id, obj] of this.renderObjects) {
      obj.mesh.visible = visibleIds.has(id);
    }

    this.renderer.render(this.scene, this.camera);

    const t1 = performance.now();
    this.overlay.record(t1 - t0, drawCalls, triangleCount);
    this.overlay.recordVisibleEmbodiments(payloads.length);
    this.overlay.recordMemory(this.estimateGPUMemory());
    this.overlay.recordTextures(this.getTextureCount());
    this.overlay.recordPrograms(this.shaderCache.size);
    this.stats = this.overlay.getStats();
  }

  private getOrCreateRenderObject(payload: RenderPayload): ThreeRenderObject | null {
    const { asset, material, shader, lod, transform, frameState } = payload;
    const cacheKey = `${asset.id}_${material.id}_${shader.id}_${lod?.assetId || 'base'}`;

    let obj = this.renderObjects.get(cacheKey);
    if (obj) {
      if (transform) {
        obj.mesh.position.set(transform.position[0], transform.position[1], transform.position[2]);
        obj.mesh.rotation.set(transform.rotation[0], transform.rotation[1], transform.rotation[2]);
        obj.mesh.scale.set(transform.scale[0], transform.scale[1], transform.scale[2]);
      }
      this.updateMaterial(obj.mesh.material as THREE.Material, material, frameState);
      return obj;
    }

    const geometry = this.getOrCreateGeometry(asset, lod);
    const threeMaterial = this.getOrCreateMaterial(material, shader, frameState);
    if (!geometry || !threeMaterial) return null;

    const mesh = new THREE.Mesh(geometry, threeMaterial);
    mesh.frustumCulled = true;
    mesh.castShadow = false;
    mesh.receiveShadow = false;

    if (transform) {
      mesh.position.set(transform.position[0], transform.position[1], transform.position[2]);
      mesh.rotation.set(transform.rotation[0], transform.rotation[1], transform.rotation[2]);
      mesh.scale.set(transform.scale[0], transform.scale[1], transform.scale[2]);
    }

    this.scene!.add(mesh);

    obj = {
      mesh,
      assetId: asset.id,
      materialId: material.id,
      shaderId: shader.id,
      lodLevel: lod ? 1 : 0,
    };

    this.renderObjects.set(cacheKey, obj);
    return obj;
  }

  private getOrCreateGeometry(asset: AssetDescriptor, lod?: { assetId: string }): THREE.BufferGeometry | undefined {
    const geoKey = lod ? `${asset.id}_lod_${lod.assetId}` : asset.id;
    let geometry = this.geometryCache.get(geoKey);

    if (geometry) return geometry;

    geometry = this.createGeometryFromAsset(asset);
    if (!geometry) return undefined;

    this.geometryCache.set(geoKey, geometry);
    return geometry;
  }

  private createGeometryFromAsset(asset: AssetDescriptor): THREE.BufferGeometry | undefined {
    const metadata = asset.metadata || {};
    const type = metadata.geometryType as string || 'box';
    const params = metadata.geometryParams as Record<string, number> || {};

    switch (type) {
      case 'sphere':
        return new THREE.SphereGeometry(
          params.radius || 1,
          params.widthSegments || 16,
          params.heightSegments || 16
        );
      case 'box':
        return new THREE.BoxGeometry(
          params.width || 1,
          params.height || 1,
          params.depth || 1
        );
      case 'octahedron':
        return new THREE.OctahedronGeometry(params.radius || 1, params.detail || 0);
      case 'tetrahedron':
        return new THREE.TetrahedronGeometry(params.radius || 1, params.detail || 0);
      case 'icosahedron':
        return new THREE.IcosahedronGeometry(params.radius || 1, params.detail || 0);
      case 'cone':
        return new THREE.ConeGeometry(
          params.radius || 1,
          params.height || 1,
          params.radialSegments || 8
        );
      case 'cylinder':
        return new THREE.CylinderGeometry(
          params.radiusTop || 1,
          params.radiusBottom || 1,
          params.height || 1,
          params.radialSegments || 8
        );
      case 'plane':
        return new THREE.PlaneGeometry(params.width || 1, params.height || 1);
      case 'torus':
        return new THREE.TorusGeometry(
          params.radius || 1,
          params.tube || 0.4,
          params.radialSegments || 8,
          params.tubularSegments || 16
        );
      default:
        return new THREE.BoxGeometry(1, 1, 1);
    }
  }

  private getOrCreateMaterial(
    material: MaterialDescriptor,
    shader: ShaderDescriptor,
    frameState: FrameState
  ): THREE.Material | null {
    const matKey = `${material.id}_${shader.id}`;
    let threeMaterial = this.materialCache.get(matKey);

    if (threeMaterial) {
      this.updateMaterial(threeMaterial, material, frameState);
      return threeMaterial;
    }

    if (material.shaderId && shader.id) {
      threeMaterial = this.createShaderMaterial(material, shader, frameState);
    } else {
      threeMaterial = this.createStandardMaterial(material);
    }

    if (threeMaterial) {
      this.materialCache.set(matKey, threeMaterial);
    }

    return threeMaterial;
  }

  private createStandardMaterial(descriptor: MaterialDescriptor): THREE.MeshStandardMaterial {
    const uniforms = descriptor.uniforms || {};
    const getUniform = (key: string, fallback: any) => uniforms[key]?.value ?? fallback;

    const material = new THREE.MeshStandardMaterial({
      color: getUniform('color', 0x00ff77),
      roughness: getUniform('roughness', 0.7),
      metalness: getUniform('metalness', 0.3),
      emissive: getUniform('emissive', 0x000000),
      emissiveIntensity: getUniform('emissiveIntensity', 0),
      transparent: descriptor.transparent ?? false,
      opacity: getUniform('opacity', 1),
      depthWrite: descriptor.depthWrite ?? true,
      depthTest: descriptor.depthTest ?? true,
      blending: this.getBlending(descriptor.blending),
      side: this.getSide(descriptor.side),
      toneMapped: true,
      flatShading: false,
      vertexColors: true,
    });

    material.name = descriptor.id;
    material.userData.descriptor = descriptor;

    return material;
  }

  private createShaderMaterial(
    material: MaterialDescriptor,
    shader: ShaderDescriptor,
    frameState: FrameState
  ): THREE.ShaderMaterial {
    const shaderKey = shader.id;
    let shaderMaterial = this.shaderCache.get(shaderKey);

    if (shaderMaterial) {
      this.updateShaderUniforms(shaderMaterial, material, frameState);
      return shaderMaterial;
    }

    const uniforms = this.parseUniforms(material.uniforms || {});
    this.addFrameStateUniforms(uniforms, frameState);

    shaderMaterial = new THREE.ShaderMaterial({
      vertexShader: shader.vertex,
      fragmentShader: shader.fragment,
      uniforms,
      transparent: material.transparent ?? false,
      depthWrite: material.depthWrite ?? true,
      depthTest: material.depthTest ?? true,
      blending: this.getBlending(material.blending),
      side: this.getSide(material.side),
      toneMapped: false,
      vertexColors: true,
    });

    shaderMaterial.name = material.id;
    this.shaderCache.set(shaderKey, shaderMaterial);
    return shaderMaterial;
  }

  private parseUniforms(uniforms: Record<string, { value: unknown; type?: string }>): Record<string, THREE.IUniform> {
    const result: Record<string, THREE.IUniform> = {};
    for (const [key, uniform] of Object.entries(uniforms)) {
      const value = uniform.value;
      if (value && typeof value === 'object') {
        if (value instanceof THREE.Color) {
          result[key] = { value: value.clone() };
        } else if (value instanceof THREE.Vector2) {
          result[key] = { value: value.clone() };
        } else if (value instanceof THREE.Vector3) {
          result[key] = { value: value.clone() };
        } else if (value instanceof THREE.Matrix4) {
          result[key] = { value: value.clone() };
        } else if (Array.isArray(value)) {
          if (value.length === 3) {
            result[key] = { value: new THREE.Vector3(value[0], value[1], value[2]) };
          } else if (value.length === 2) {
            result[key] = { value: new THREE.Vector2(value[0], value[1]) };
          } else if (value.length === 16) {
            result[key] = { value: new THREE.Matrix4().fromArray(value) };
          } else {
            result[key] = { value };
          }
        } else {
          result[key] = { value };
        }
      } else if (typeof value === 'number' || typeof value === 'boolean') {
        result[key] = { value };
      } else {
        result[key] = { value };
      }
    }
    return result;
  }

  private addFrameStateUniforms(uniforms: Record<string, THREE.IUniform>, frameState: FrameState): void {
    uniforms.u_frameState = {
      value: new THREE.Vector4(
        frameState.visual.presence,
        frameState.visual.energy,
        frameState.visual.focus,
        frameState.visual.activity
      )
    };
    uniforms.u_time = { value: frameState.metadata.timestamp / 1000 };
    uniforms.u_correlationId = { value: frameState.metadata.correlationId };
  }

  private updateMaterial(material: THREE.Material, descriptor: MaterialDescriptor, frameState: FrameState): void {
    if (material instanceof THREE.MeshStandardMaterial) {
      const uniforms = descriptor.uniforms || {};
      const getUniform = (key: string, fallback: any) => uniforms[key]?.value ?? fallback;

      material.color.set(getUniform('color', 0x00ff77));
      material.roughness = getUniform('roughness', 0.7);
      material.metalness = getUniform('metalness', 0.3);
      material.emissive.set(getUniform('emissive', 0x000000));
      material.emissiveIntensity = getUniform('emissiveIntensity', 0);
      material.opacity = getUniform('opacity', 1);
      material.transparent = descriptor.transparent ?? false;
      material.depthWrite = descriptor.depthWrite ?? true;
      material.needsUpdate = true;
    } else if (material instanceof THREE.ShaderMaterial) {
      this.updateShaderUniforms(material, descriptor, frameState);
    }
  }

  private updateShaderUniforms(material: THREE.ShaderMaterial, descriptor: MaterialDescriptor, frameState: FrameState): void {
    const uniforms = descriptor.uniforms || {};
    for (const [key, uniform] of Object.entries(uniforms)) {
      if (material.uniforms[key]) {
        const value = uniform.value;
        if (value instanceof THREE.Color) {
          material.uniforms[key].value.copy(value);
        } else if (value instanceof THREE.Vector2) {
          material.uniforms[key].value.copy(value);
        } else if (value instanceof THREE.Vector3) {
          material.uniforms[key].value.copy(value);
        } else if (typeof value === 'number') {
          material.uniforms[key].value = value;
        } else {
          material.uniforms[key].value = value;
        }
      }
    }

    if (material.uniforms.u_frameState) {
      material.uniforms.u_frameState.value.set(
        frameState.visual.presence,
        frameState.visual.energy,
        frameState.visual.focus,
        frameState.visual.activity
      );
    }
    if (material.uniforms.u_time) {
      material.uniforms.u_time.value = frameState.metadata.timestamp / 1000;
    }
    material.needsUpdate = true;
  }

  private getBlending(blending?: 'normal' | 'additive' | 'multiply'): THREE.Blending {
    switch (blending) {
      case 'additive': return THREE.AdditiveBlending;
      case 'multiply': return THREE.MultiplyBlending;
      default: return THREE.NormalBlending;
    }
  }

  private getSide(side?: 'front' | 'back' | 'double'): THREE.Side {
    switch (side) {
      case 'back': return THREE.BackSide;
      case 'double': return THREE.DoubleSide;
      default: return THREE.FrontSide;
    }
  }

  private estimateGPUMemory(): number {
    let bytes = 0;
    for (const geom of this.geometryCache.values()) {
      const pos = geom.attributes.position;
      if (pos) bytes += pos.count * 3 * 4;
      const norm = geom.attributes.normal;
      if (norm) bytes += norm.count * 3 * 4;
      const uv = geom.attributes.uv;
      if (uv) bytes += uv.count * 2 * 4;
      const color = geom.attributes.color;
      if (color) bytes += color.count * 3 * 4;
      if (geom.index) bytes += geom.index.count * 4;
    }
    for (const mat of this.materialCache.values()) {
      bytes += 1024;
    }
    for (const mat of this.shaderCache.values()) {
      bytes += 2048;
    }
    return bytes;
  }

  private getTextureCount(): number {
    let count = 0;
    for (const mat of this.materialCache.values()) {
      if (mat instanceof THREE.MeshStandardMaterial) {
        if (mat.map) count++;
        if (mat.normalMap) count++;
        if (mat.roughnessMap) count++;
        if (mat.metalnessMap) count++;
        if (mat.emissiveMap) count++;
        if (mat.aoMap) count++;
        if (mat.envMap) count++;
      }
    }
    for (const mat of this.shaderCache.values()) {
      for (const uniform of Object.values(mat.uniforms)) {
        const val = uniform.value;
        if (val && typeof val === 'object' && 'isTexture' in val && (val as any).isTexture) count++;
      }
    }
    return count;
  }

  dispose(): void {
    if (this.animationFrameId && typeof globalThis !== 'undefined' && typeof globalThis.cancelAnimationFrame === 'function') {
      globalThis.cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }

    for (const [, obj] of this.renderObjects) {
      this.scene?.remove(obj.mesh);
      obj.mesh.geometry.dispose();
      if (Array.isArray(obj.mesh.material)) {
        obj.mesh.material.forEach((m: THREE.Material) => m.dispose());
      } else {
        obj.mesh.material.dispose();
      }
    }
    this.renderObjects.clear();

    for (const [, geom] of this.geometryCache) {
      geom.dispose();
    }
    this.geometryCache.clear();

    for (const [, mat] of this.materialCache) {
      mat.dispose();
    }
    this.materialCache.clear();

    for (const [, mat] of this.shaderCache) {
      mat.dispose();
    }
    this.shaderCache.clear();

    this.lodCache.clear();

    this.renderer?.dispose();
    this.renderer = null;
    this.scene = null;
    this.camera = null;
    this.ctx = null;
    this.isInitialized = false;
  }

  getStats() {
    if (!this.stats) this.stats = this.overlay.getStats();
    return {
      ...this.stats,
      renderObjects: this.renderObjects.size,
      geometries: this.geometryCache.size,
      materials: this.materialCache.size,
      shaders: this.shaderCache.size,
      estimatedGPUMemory: this.estimateGPUMemory(),
    };
  }
}

export { Renderer } from './Renderer';