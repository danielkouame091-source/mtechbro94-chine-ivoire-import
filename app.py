import sys
import math
import numpy as np
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import (
    Point3, Vec3, Vec4, DirectionalLight, AmbientLight, 
    Material, NodePath, CardMaker, Texture
)
import simplepbr
import trimesh

# =====================================================================
# 1. PANDA3D REAL-TIME INTERACTIVE VIEWPER & SCENE GENERATOR
# =====================================================================
class Interactive3DProfile(ShowBase):
    def __init__(self):
        super().__init__()
        
        # Activer le pipeline de rendu PBR (Physically Based Rendering)
        self.pipeline = simplepbr.init(enable_shadows=True, max_lights=4)
        
        # Configuration de la fenêtre et de la caméra
        self.disableMouse()
        self.camera.setPos(0, -6.5, 1.2)
        self.camera.lookAt(0, 0, 0)
        self.setBackgroundColor(0.04, 0.06, 0.10, 1)

        # Installation des lumières dynamiques
        self.setup_lighting()
        
        # Création de la géométrie de l'Avatar / Scène 3D
        self.avatar_node = self.create_stylized_avatar()
        self.avatar_node.reparentTo(self.render)
        
        # Ajout des tâches d'animation interactives
        self.taskMgr.add(self.rotate_and_pulse_task, "RotateAndPulseTask")
        
        print("✅ Application Panda3D initialisée avec succès.")

    def setup_lighting(self):
        # Lumière Ambiante Douce
        amb_light = AmbientLight("amb_light")
        amb_light.setColor(Vec4(0.15, 0.20, 0.30, 1.0))
        amb_np = self.render.attachNewNode(amb_light)
        self.render.setLight(amb_np)

        # Lumière Principale (Key Light - Cyan/Bleu)
        dir_light_1 = DirectionalLight("dir_light_1")
        dir_light_1.setColor(Vec4(0.2, 0.7, 1.0, 1.0))
        dir_np_1 = self.render.attachNewNode(dir_light_1)
        dir_np_1.setHpr(-45, -35, 0)
        self.render.setLight(dir_np_1)

        # Lumière de Contour (Rim Light - Émeraude)
        dir_light_2 = DirectionalLight("dir_light_2")
        dir_light_2.setColor(Vec4(0.1, 0.9, 0.5, 1.0))
        dir_np_2 = self.render.attachNewNode(dir_light_2)
        dir_np_2.setHpr(135, 25, 0)
        self.render.setLight(dir_np_2)

    def create_stylized_avatar(self):
        root = NodePath("AvatarRoot")
        
        # Sphère Centrale (Tête / Core)
        sphere_model = self.loader.loadModel("models/smiley")
        sphere_model.reparentTo(root)
        sphere_model.setScale(0.8)
        sphere_model.setPos(0, 0, 0)

        # Matériau PBR Moderne
        mat = Material("PBR_Glass_Metal")
        mat.setBaseColor(Vec4(0.1, 0.5, 0.9, 1.0))
        mat.setMetallic(0.85)
        mat.setRoughness(0.15)
        sphere_model.setMaterial(mat)

        # Anneaux d'interaction flottants autour du noyau
        self.rings = []
        for i in range(3):
            ring = self.loader.loadModel("models/smiley")
            ring.reparentTo(root)
            scale_x = 1.4 + (i * 0.3)
            scale_z = 0.05
            ring.setScale(scale_x, scale_x, scale_z)
            ring.setPos(0, 0, 0)
            
            ring_mat = Material(f"RingMat_{i}")
            ring_mat.setBaseColor(Vec4(0.1, 0.9, 0.6, 0.8))
            ring_mat.setMetallic(0.9)
            ring_mat.setRoughness(0.1)
            ring.setMaterial(ring_mat)
            self.rings.append(ring)

        return root

    def rotate_and_pulse_task(self, task):
        t = task.time
        # Rotation lente et fluide de la scène
        self.avatar_node.setH(t * 25.0)
        self.avatar_node.setZ(math.sin(t * 1.5) * 0.15)
        
        # Contrôle des anneaux orbitaux
        for idx, ring in enumerate(self.rings):
            direction = 1 if idx % 2 == 0 else -1
            ring.setHpr(t * 40.0 * direction, math.sin(t + idx) * 20.0, 0)

        return Task.cont


# =====================================================================
# 2. EXPORTATEUR GLTF / GLB STRUCTURÉ (POUR LE WEB THREE.JS)
# =====================================================================
def export_interactive_scene_glb(output_path="avatar_profile.glb"):
    """
    Génère et exporte la géométrie 3D avec matériaux PBR et textures 
    dans un conteneur GLB binaire prêt pour Three.js.
    """
    print(f"📦 Génération et exportation du modèle GLB vers '{output_path}'...")
    
    # Création du Noyau Icosaèdre PBR avec Trimesh
    core_mesh = trimesh.creation.icosahedron(subdivisions=3, radius=1.0)
    
    # Couleurs de sommets dynamiques (Gradient Émeraude -> Cyan)
    colors = []
    for vertex in core_mesh.vertices:
        r = int((vertex[0] + 1.0) * 0.5 * 30)
        g = int((vertex[1] + 1.0) * 0.5 * 200 + 55)
        b = int((vertex[2] + 1.0) * 0.5 * 180 + 75)
        colors.append([r, g, b, 255])
    
    core_mesh.visual.vertex_colors = np.array(colors, dtype=np.uint8)
    
    # Anneau Orbital Externe
    ring_mesh = trimesh.creation.torus(major_radius=1.6, minor_radius=0.06)
    ring_mesh.apply_translation([0, 0, 0])
    
    # Fusion de la Scène
    scene = trimesh.Scene([core_mesh, ring_mesh])
    
    # Export Binaire GLB
    glb_data = scene.export(file_type="glb")
    with open(output_path, "wb") as f:
        f.write(glb_data)
        
    print(f"✅ Fichier GLB exporté avec succès : {output_path}")


if __name__ == "__main__":
    # 1. Exporter le fichier GLB pour le Web
    export_interactive_scene_glb("avatar_profile.glb")
    
    # 2. Lancer la prévisualisation temps réel Panda3D
    print("🚀 Lancement du moteur Panda3D...")
    app = Interactive3DProfile()
    app.run()
