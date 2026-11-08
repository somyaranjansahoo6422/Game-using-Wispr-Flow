import asyncio
from contextlib import asynccontextmanager
import math
import random
import re

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


# ============================================================
# VECTOR // TACTICAL AIR COMBAT
# Game prototype:
# - Select F-35 or Su-57
# - Select a theater
# - Complete combat objectives
# - Protect / strike fictional enemy assets
# - No clearance log
# - 3D terrain, shadows, animated aircraft, characters and cat
#
# High-fidelity assets can be dropped into /static/assets later:
#   jets/f35.glb
#   jets/su57.glb
#   maps/caucasus.glb
#   maps/persian_gulf.glb
#   maps/black_sea_georgia.glb
# ============================================================

THEATERS = {
    "caucasus": {
        "name": "CAUCASUS",
        "subtitle": "Mountain frontier / DCS-style theater",
        "terrain": "mountains",
        "sky": "#07111d",
        "fog": "#08111a",
        "objective_pool": [
            "Intercept hostile scouts",
            "Protect the mountain forward base",
            "Destroy the fictional hostile radar site",
        ],
    },
    "persian_gulf": {
        "name": "PERSIAN GULF",
        "subtitle": "Desert coast / carrier approach",
        "terrain": "desert",
        "sky": "#1b1820",
        "fog": "#17151a",
        "objective_pool": [
            "Intercept incoming hostile aircraft",
            "Protect the coastal fleet",
            "Destroy the fictional hostile command node",
        ],
    },
    "black_sea_georgia": {
        "name": "BLACK SEA & GEORGIA",
        "subtitle": "Coastal mountains / maritime theater",
        "terrain": "coast",
        "sky": "#06151b",
        "fog": "#071419",
        "objective_pool": [
            "Intercept hostile aircraft",
            "Protect the coastal airbase",
            "Destroy the fictional hostile logistics site",
        ],
    },
}

JETS = {
    "f35": {
        "name": "LOCKHEED MARTIN F-35",
        "short": "F-35",
        "role": "Stealth multirole",
        "speed": 1.25,
        "turn": 1.18,
        "weapons": 5,
        "color": 0x607080,
    },
    "su57": {
        "name": "SUKHOI SU-57",
        "short": "SU-57",
        "role": "Air-superiority multirole",
        "speed": 1.38,
        "turn": 1.30,
        "weapons": 6,
        "color": 0x34414d,
    },
}


class Command(BaseModel):
    action: str
    value: str | None = None


state = {
    "jet": "f35",
    "theater": "caucasus",
    "score": 0,
    "round": 1,
    "mission_complete": False,
    "game_over": False,
    "health": 100,
    "ammo": 100,
    "objective_index": 0,
    "message": "Select a jet and theater, then launch.",
    "player": {
        "x": 0,
        "y": 7,
        "z": 18,
        "heading": 0,
        "pitch": 0,
        "roll": 0,
    },
    "enemies": [],
    "bases": [],
    "effects": [],
    "characters": {
        "boy": {"name": "KAI", "age": 22, "mood": "focused"},
        "girl": {"name": "NOVA", "age": 23, "mood": "focused", "face_visible": False},
        "cat": {"name": "JET", "mood": "excited"},
    },
}


def make_enemy(index: int):
    angle = (index / 5.0) * math.tau + random.uniform(-0.4, 0.4)
    radius = random.uniform(18, 30)
    return {
        "id": f"HOSTILE-{index + 1}",
        "x": math.cos(angle) * radius,
        "y": random.uniform(4, 12),
        "z": math.sin(angle) * radius,
        "heading": random.uniform(0, 360),
        "health": 100,
        "speed": random.uniform(0.10, 0.20),
        "alive": True,
        "kind": random.choice(["interceptor", "scout"]),
    }


def make_base(index: int):
    angle = (index / 3.0) * math.tau + 0.8
    radius = 32
    return {
        "id": f"HOSTILE-BASE-{index + 1}",
        "x": math.cos(angle) * radius,
        "z": math.sin(angle) * radius,
        "health": 100,
        "alive": True,
    }


def reset_round():
    state["mission_complete"] = False
    state["game_over"] = False
    state["health"] = 100
    state["ammo"] = 100
    state["objective_index"] = 0
    state["message"] = "Mission ready. Launch when prepared."
    state["player"] = {
        "x": 0,
        "y": 7,
        "z": 18,
        "heading": 0,
        "pitch": 0,
        "roll": 0,
    }
    state["enemies"] = [make_enemy(i) for i in range(5)]
    state["bases"] = [make_base(i) for i in range(3)]
    state["effects"] = []


def current_objective():
    theater = THEATERS[state["theater"]]
    pool = theater["objective_pool"]
    if state["objective_index"] >= len(pool):
        return "Return to base"
    return pool[state["objective_index"]]


def objective_progress():
    objective = current_objective().lower()

    if "destroy" in objective:
        alive = sum(1 for b in state["bases"] if b["alive"])
        return f"{3 - alive}/3 hostile sites neutralized"
    if "protect" in objective:
        return f"BASE INTEGRITY {max(0, state['health'])}%"
    alive = sum(1 for e in state["enemies"] if e["alive"])
    return f"{5 - alive}/5 hostile aircraft intercepted"


async def game_loop():
    while True:
        await asyncio.sleep(0.08)

        if state["game_over"] or state["mission_complete"]:
            continue

        # Small autonomous movement creates a live battlefield feel.
        p = state["player"]
        jet = JETS[state["jet"]]
        p["x"] += math.sin(math.radians(p["heading"])) * 0.035 * jet["speed"]
        p["z"] += math.cos(math.radians(p["heading"])) * 0.035 * jet["speed"]

        for enemy in state["enemies"]:
            if not enemy["alive"]:
                continue
            enemy["heading"] = (enemy["heading"] + random.uniform(-1.5, 1.5)) % 360
            enemy["x"] += math.sin(math.radians(enemy["heading"])) * enemy["speed"]
            enemy["z"] += math.cos(math.radians(enemy["heading"])) * enemy["speed"]

            # Fictional combat pressure; not a real-world model.
            d = math.hypot(enemy["x"] - p["x"], enemy["z"] - p["z"])
            if d < 4.5 and random.random() < 0.025:
                state["health"] -= 3
                state["message"] = "MISSILE WARNING // break contact"

        if state["health"] <= 0:
            state["health"] = 0
            state["game_over"] = True
            state["message"] = "AIRCRAFT LOST // ROUND FAILED"


@asynccontextmanager
async def lifespan(app: FastAPI):
    reset_round()
    task = asyncio.create_task(game_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="VECTOR Tactical Air Combat", lifespan=lifespan)


@app.get("/api/state")
async def get_state():
    return {
        **state,
        "jet_info": JETS[state["jet"]],
        "theater_info": THEATERS[state["theater"]],
        "objective": current_objective(),
        "progress": objective_progress(),
    }


@app.post("/api/command")
async def command(cmd: Command):
    action = cmd.action
    value = cmd.value or ""

    if action == "select_jet" and value in JETS:
        state["jet"] = value
        state["message"] = f"{JETS[value]['name']} selected."
        return {"ok": True, "message": state["message"]}

    if action == "select_theater" and value in THEATERS:
        state["theater"] = value
        state["message"] = f"{THEATERS[value]['name']} theater selected."
        reset_round()
        return {"ok": True, "message": state["message"]}

    if action == "launch":
        reset_round()
        state["message"] = f"ROUND {state['round']} // {JETS[state['jet']]['short']} // ENGAGED"
        return {"ok": True, "message": state["message"]}

    if action == "maneuver":
        p = state["player"]
        if value == "left":
            p["heading"] = (p["heading"] - 18) % 360
            p["roll"] = -28
        elif value == "right":
            p["heading"] = (p["heading"] + 18) % 360
            p["roll"] = 28
        elif value == "up":
            p["pitch"] = min(25, p["pitch"] + 8)
            p["y"] = min(18, p["y"] + 0.8)
        elif value == "down":
            p["pitch"] = max(-25, p["pitch"] - 8)
            p["y"] = max(2.5, p["y"] - 0.8)
        state["message"] = f"MANEUVER // {value.upper()}"
        return {"ok": True, "message": state["message"]}

    if action == "fire":
        if state["ammo"] <= 0:
            state["message"] = "WEAPON BAY EMPTY"
            return {"ok": False, "message": state["message"]}

        state["ammo"] -= 10
        p = state["player"]

        live_enemies = [
            e for e in state["enemies"]
            if e["alive"]
        ]
        live_bases = [
            b for b in state["bases"]
            if b["alive"]
        ]

        target = None
        candidates = live_enemies + live_bases
        if candidates:
            target = min(
                candidates,
                key=lambda obj: math.hypot(
                    obj["x"] - p["x"],
                    obj["z"] - p["z"],
                ),
            )

        if target:
            d = math.hypot(target["x"] - p["x"], target["z"] - p["z"])
            if d < 28:
                target["health"] -= 55
                state["effects"].append({
                    "kind": "impact",
                    "x": target["x"],
                    "y": target.get("y", 0),
                    "z": target["z"],
                    "life": 1,
                })

                if target["health"] <= 0:
                    target["alive"] = False
                    state["score"] += 250
                    state["message"] = f"TARGET NEUTRALIZED // +250"
                else:
                    state["message"] = "HIT CONFIRMED"
            else:
                state["message"] = "SHOT OUT OF RANGE"
        else:
            state["message"] = "NO LIVE TARGET"

        # Advance objective when the relevant fictional target set is complete.
        obj = current_objective().lower()
        if "intercept" in obj:
            if not any(e["alive"] for e in state["enemies"]):
                state["objective_index"] = 1
        elif "destroy" in obj:
            if not any(b["alive"] for b in state["bases"]):
                state["objective_index"] = 2

        # Once all major tasks are completed, award round victory.
        if (
            not any(e["alive"] for e in state["enemies"])
            and not any(b["alive"] for b in state["bases"])
        ):
            state["mission_complete"] = True
            state["score"] += 1000
            state["message"] = "ROUND WON // TOP-GUN-STYLE VICTORY SEQUENCE READY"

        return {"ok": True, "message": state["message"]}

    if action == "reset":
        state["score"] = 0
        state["round"] = 1
        reset_round()
        state["message"] = "SYSTEM RESET"
        return {"ok": True, "message": state["message"]}

    return {"ok": False, "message": "UNKNOWN COMMAND"}


@app.get("/", response_class=HTMLResponse)
async def index():
    return r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VECTOR // TACTICAL AIR COMBAT</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<style>
*{box-sizing:border-box}
html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#05070a;color:#e9f4ff;font-family:Inter,Segoe UI,Arial,sans-serif}
button{font:inherit}
#scene{position:fixed;inset:0}
.hud{position:fixed;inset:0;pointer-events:none}
.topbar{height:74px;background:linear-gradient(180deg,rgba(4,8,13,.94),rgba(4,8,13,.55));display:flex;align-items:center;justify-content:space-between;padding:0 22px;border-bottom:1px solid rgba(135,190,255,.18)}
.brand{letter-spacing:4px;font-weight:800;color:#d7efff}
.brand span{color:#58c7ff}
.status{display:flex;gap:20px;align-items:center;font-size:12px;letter-spacing:1px}
.pill{padding:8px 11px;border:1px solid rgba(125,194,255,.3);background:rgba(8,18,28,.72);border-radius:5px}
.green{color:#71ffb1}.yellow{color:#ffe36e}.red{color:#ff7777}
.left{position:fixed;left:18px;top:92px;width:285px;pointer-events:auto}
.right{position:fixed;right:18px;top:92px;width:305px;pointer-events:auto}
.card{background:rgba(5,10,16,.83);border:1px solid rgba(130,190,255,.22);box-shadow:0 12px 40px rgba(0,0,0,.28);backdrop-filter:blur(10px);border-radius:8px;margin-bottom:12px;padding:14px}
.card h3{margin:0 0 10px;font-size:11px;letter-spacing:2px;color:#9acff2}
.row{display:flex;gap:8px;margin:7px 0}
.btn{flex:1;border:1px solid rgba(125,194,255,.26);background:#0b1520;color:#cdeaff;padding:9px;border-radius:5px;cursor:pointer;transition:.18s}
.btn:hover{border-color:#55c8ff;transform:translateY(-1px)}
.btn.active{background:#12334a;border-color:#54c7ff;color:white;box-shadow:0 0 18px rgba(75,190,255,.16)}
.launch{width:100%;background:linear-gradient(90deg,#1b638c,#0d3d5d);border-color:#56cbff;font-weight:800;letter-spacing:2px}
.stat{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.06);font-size:12px}
.stat:last-child{border-bottom:0}
.objective{font-size:13px;line-height:1.45;color:#d9edff}
.progress{margin-top:10px;color:#77d9ff;font-size:11px}
.controls{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:10px}
.controls .wide{grid-column:1/4}
.message{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);min-width:430px;text-align:center;padding:11px 18px;background:rgba(4,10,15,.9);border:1px solid rgba(98,199,255,.3);border-radius:5px;font-size:12px;letter-spacing:1.2px}
.crosshair{position:fixed;left:50%;top:50%;width:54px;height:54px;transform:translate(-50%,-50%);border:1px solid rgba(130,220,255,.38);border-radius:50%}
.crosshair:before,.crosshair:after{content:"";position:absolute;background:#8bdcff}
.crosshair:before{width:74px;height:1px;left:-11px;top:26px}
.crosshair:after{height:74px;width:1px;left:26px;top:-11px}
.target-box{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);width:120px;height:90px;border:1px dashed rgba(255,100,100,.7);display:none}
.character-strip{display:flex;gap:8px;align-items:center}
.avatar{width:50px;height:50px;border-radius:7px;background:linear-gradient(145deg,#263747,#080c12);display:grid;place-items:center;font-weight:900;font-size:18px}
.avatar.girl{position:relative}.avatar.girl:after{content:"";position:absolute;inset:0;background:rgba(3,5,8,.72);border-radius:7px}
.avatar.cat{font-size:26px;background:#111}
.character-name{font-size:11px;color:#a8d9f6}.character-mood{font-size:10px;color:#6f8291;margin-top:3px}
.victory{position:fixed;inset:0;background:rgba(0,0,0,.78);display:none;align-items:center;justify-content:center;z-index:20}
.victory.show{display:flex}
.victory-card{width:min(680px,90vw);padding:32px;border:1px solid #66d3ff;background:linear-gradient(145deg,#08131d,#020507);text-align:center;box-shadow:0 0 80px rgba(46,169,255,.25)}
.victory-card h1{font-size:32px;letter-spacing:5px;margin:0 0 8px}.victory-card p{color:#9dc7dc}
.small{font-size:10px;color:#718494;line-height:1.5}
</style>
</head>
<body>
<div id="scene"></div>

<div class="hud">
  <div class="topbar">
    <div class="brand">VECTOR <span>// TACTICAL AIR COMBAT</span></div>
    <div class="status">
      <div class="pill">ROUND <b id="round">1</b></div>
      <div class="pill">SCORE <b id="score">0</b></div>
      <div class="pill green">SYSTEM <b>ONLINE</b></div>
    </div>
  </div>

  <div class="left">
    <div class="card">
      <h3>SELECT AIRCRAFT</h3>
      <div class="row">
        <button class="btn" id="f35" onclick="selectJet('f35')">F-35</button>
        <button class="btn" id="su57" onclick="selectJet('su57')">SU-57</button>
      </div>
      <div class="small">Different flight handling, speed and combat loadout.</div>
    </div>

    <div class="card">
      <h3>THEATER</h3>
      <div class="row">
        <button class="btn" id="caucasus" onclick="selectTheater('caucasus')">CAUCASUS</button>
      </div>
      <div class="row">
        <button class="btn" id="persian_gulf" onclick="selectTheater('persian_gulf')">PERSIAN GULF</button>
      </div>
      <div class="row">
        <button class="btn" id="black_sea_georgia" onclick="selectTheater('black_sea_georgia')">BLACK SEA</button>
      </div>
    </div>

    <div class="card">
      <h3>MISSION</h3>
      <div class="objective" id="objective">Select a mission loadout.</div>
      <div class="progress" id="progress">---</div>
      <button class="btn launch" onclick="command('launch')">LAUNCH ROUND</button>
    </div>
  </div>

  <div class="right">
    <div class="card">
      <h3>AIRCRAFT STATUS</h3>
      <div class="stat"><span>JET</span><b id="jet">---</b></div>
      <div class="stat"><span>HEALTH</span><b id="health">100%</b></div>
      <div class="stat"><span>AMMO</span><b id="ammo">100</b></div>
      <div class="stat"><span>ROLE</span><b id="role">---</b></div>
    </div>

    <div class="card">
      <h3>CREW // PRIVATE FLIGHT DECK</h3>
      <div class="character-strip">
        <div class="avatar">K</div>
        <div><div class="character-name">KAI // PILOT</div><div class="character-mood" id="boyMood">Focused</div></div>
      </div>
      <div class="character-strip" style="margin-top:9px">
        <div class="avatar girl"></div>
        <div><div class="character-name">NOVA // WSO</div><div class="character-mood">Face permanently concealed</div></div>
      </div>
      <div class="character-strip" style="margin-top:9px">
        <div class="avatar cat">🐈‍⬛</div>
        <div><div class="character-name">JET // BLACK CAT</div><div class="character-mood">Kai's devoted companion</div></div>
      </div>
    </div>

    <div class="card">
      <h3>FLIGHT CONTROLS</h3>
      <div class="controls">
        <button class="btn" onclick="command('maneuver','left')">◀ LEFT</button>
        <button class="btn" onclick="command('maneuver','up')">▲ CLIMB</button>
        <button class="btn" onclick="command('maneuver','right')">RIGHT ▶</button>
        <button class="btn" onclick="command('maneuver','down')">▼ DIVE</button>
        <button class="btn wide" style="background:#401820;border-color:#c85c6b" onclick="command('fire')">FIRE WEAPON</button>
      </div>
    </div>
  </div>

  <div class="crosshair"></div>
  <div class="target-box" id="targetBox"></div>
  <div class="message" id="message">Select a jet and theater, then launch.</div>
</div>

<div class="victory" id="victory">
  <div class="victory-card">
    <h1>ROUND WON</h1>
    <p id="victoryText">Mission complete.</p>
    <p style="font-size:13px;color:#65cfff">TOP-GUN-STYLE VICTORY SEQUENCE</p>
    <div style="font-size:54px;margin:15px 0">🕶️ ✈️</div>
    <button class="btn launch" onclick="closeVictory();command('launch')">FLY AGAIN</button>
  </div>
</div>

<script>
const root = document.getElementById("scene");
const state = { aircraft: null, enemies: new Map(), bases: new Map(), effects: [] };
let scene, camera, renderer, clock, playerMesh;
let enemyMeshes = new Map(), baseMeshes = new Map(), terrainGroup;
let selectedJet = "f35", selectedTheater = "caucasus";

function init3D(){
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(55, innerWidth/innerHeight, .1, 1000);
  camera.position.set(0, 22, 38);
  camera.lookAt(0, 5, 0);

  renderer = new THREE.WebGLRenderer({antialias:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));
  renderer.setSize(innerWidth,innerHeight);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  root.appendChild(renderer.domElement);

  clock = new THREE.Clock();

  const hemi = new THREE.HemisphereLight(0x9fc9e8,0x152019,1.15);
  scene.add(hemi);
  const sun = new THREE.DirectionalLight(0xffffff,2.1);
  sun.position.set(-40,70,25);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048,2048);
  sun.shadow.camera.left = -80; sun.shadow.camera.right = 80;
  sun.shadow.camera.top = 80; sun.shadow.camera.bottom = -80;
  scene.add(sun);

  buildTerrain();
  playerMesh = makeJet(selectedJet,true);
  scene.add(playerMesh);

  addClouds();
  animate();
}

function clearGroup(){
  if(terrainGroup) scene.remove(terrainGroup);
  enemyMeshes.forEach(m=>scene.remove(m));
  baseMeshes.forEach(m=>scene.remove(m));
  enemyMeshes.clear(); baseMeshes.clear();
}

function buildTerrain(){
  if(terrainGroup) scene.remove(terrainGroup);
  terrainGroup = new THREE.Group();

  const theater = selectedTheater;
  const groundColor = theater==="persian_gulf" ? 0x806f55 : theater==="black_sea_georgia" ? 0x234d50 : 0x304b38;
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(150,150,60,60),
    new THREE.MeshStandardMaterial({color:groundColor,roughness:.96,metalness:.02})
  );
  ground.rotation.x=-Math.PI/2;
  ground.receiveShadow=true;
  terrainGroup.add(ground);

  // Procedural terrain gives the prototype a real 3D surface now.
  // Replace this group with licensed GLB/terrain tiles for production maps.
  if(theater==="caucasus" || theater==="black_sea_georgia"){
    for(let i=0;i<28;i++){
      const h=4+Math.random()*13;
      const mountain=new THREE.Mesh(
        new THREE.ConeGeometry(2+Math.random()*4,h,7),
        new THREE.MeshStandardMaterial({color: theater==="caucasus"?0x3b5145:0x365f63,roughness:1})
      );
      mountain.position.set((Math.random()-.5)*105,h/2,(Math.random()-.5)*105);
      mountain.castShadow=true; mountain.receiveShadow=true;
      terrainGroup.add(mountain);
    }
  }else{
    for(let i=0;i<40;i++){
      const dune=new THREE.Mesh(
        new THREE.SphereGeometry(2+Math.random()*5,12,6),
        new THREE.MeshStandardMaterial({color:0x806d4c,roughness:1})
      );
      dune.scale.y=.25;
      dune.position.set((Math.random()-.5)*120,.4,(Math.random()-.5)*120);
      dune.receiveShadow=true; terrainGroup.add(dune);
    }
  }

  // Runways / tactical pads
  for(let i=0;i<3;i++){
    const pad=new THREE.Mesh(
      new THREE.BoxGeometry(16,.18,3),
      new THREE.MeshStandardMaterial({color:0x252c31,roughness:.9})
    );
    pad.position.set(-35+i*35,.12,20);
    pad.receiveShadow=true; terrainGroup.add(pad);
  }

  scene.add(terrainGroup);
}

function makeJet(type,player=false){
  const g=new THREE.Group();
  const c=JETS_CLIENT[type]||JETS_CLIENT.f35;
  const mat=new THREE.MeshStandardMaterial({color:c.color,metalness:.7,roughness:.32});
  const dark=new THREE.MeshStandardMaterial({color:0x101820,metalness:.6,roughness:.28});
  const body=new THREE.Mesh(new THREE.CylinderGeometry(.65,.9,5.4,10),mat);
  body.rotation.x=Math.PI/2;
  body.castShadow=true; g.add(body);

  const nose=new THREE.Mesh(new THREE.ConeGeometry(.65,2.0,10),mat);
  nose.rotation.x=-Math.PI/2; nose.position.z=-3.6;
  nose.castShadow=true; g.add(nose);

  const wing=new THREE.Mesh(new THREE.BoxGeometry(5.4,.16,1.8),mat);
  wing.position.z=.3; wing.rotation.y=.05; wing.castShadow=true; g.add(wing);

  const tail=new THREE.Mesh(new THREE.BoxGeometry(2.1,.15,1.1),dark);
  tail.position.z=1.9; tail.castShadow=true; g.add(tail);

  const canopy=new THREE.Mesh(new THREE.SphereGeometry(.58,16,8),new THREE.MeshStandardMaterial({color:0x132838,transparent:true,opacity:.82,metalness:.4,roughness:.12}));
  canopy.scale.set(1,.55,1.35); canopy.position.set(0,.48,-.8); canopy.castShadow=true; g.add(canopy);

  if(player){
    const exhaust=new THREE.Mesh(new THREE.CylinderGeometry(.32,.48,.9,12),new THREE.MeshStandardMaterial({color:0x1f7ea6,emissive:0x0c4160,emissiveIntensity:2}));
    exhaust.rotation.x=Math.PI/2; exhaust.position.z=2.95; g.add(exhaust);
  }
  return g;
}

const JETS_CLIENT={
  f35:{color:0x5e6c79},su57:{color:0x36434e}
};

function makeEnemy(){
  const g=makeJet(Math.random()<.5?"f35":"su57");
  g.scale.setScalar(.82);
  return g;
}

function makeBase(){
  const g=new THREE.Group();
  const body=new THREE.Mesh(new THREE.BoxGeometry(4,1.2,4),new THREE.MeshStandardMaterial({color:0x49323a,roughness:.8}));
  body.castShadow=true; body.receiveShadow=true; g.add(body);
  const tower=new THREE.Mesh(new THREE.CylinderGeometry(.55,.75,3.8,8),new THREE.MeshStandardMaterial({color:0x6d5056,roughness:.75}));
  tower.position.y=2.4; tower.castShadow=true; g.add(tower);
  return g;
}

function syncObjects(data){
  if(!playerMesh) return;
  const p=data.player;
  playerMesh.position.set(p.x,p.y,p.z);
  playerMesh.rotation.set(THREE.MathUtils.degToRad(-p.pitch),THREE.MathUtils.degToRad(p.heading),THREE.MathUtils.degToRad(p.roll));

  data.enemies.forEach(e=>{
    let m=enemyMeshes.get(e.id);
    if(!m){m=makeEnemy();scene.add(m);enemyMeshes.set(e.id,m);}
    m.visible=e.alive;
    m.position.set(e.x,e.y,e.z);
    m.rotation.y=THREE.MathUtils.degToRad(e.heading);
    m.traverse(o=>{if(o.isMesh)o.material.emissiveIntensity=e.alive?0:.5});
  });

  data.bases.forEach(b=>{
    let m=baseMeshes.get(b.id);
    if(!m){m=makeBase();scene.add(m);baseMeshes.set(b.id,m);}
    m.visible=b.alive;
    m.position.set(b.x,0.8,b.z);
  });

  // Chase camera gives a more game-like feel than the original radar view.
  const desired=new THREE.Vector3(p.x, p.y+12, p.z+28);
  camera.position.lerp(desired,.075);
  camera.lookAt(p.x,p.y,p.z-10);
}

function animate(){
  requestAnimationFrame(animate);
  const t=clock.getElapsedTime();
  if(playerMesh){
    playerMesh.position.y += Math.sin(t*2)*.012;
  }
  enemyMeshes.forEach((m,i)=>{
    if(m.visible)m.rotation.z=Math.sin(t*1.5+i)*.03;
  });
  renderer.render(scene,camera);
}

async function command(action,value=null){
  const res=await fetch("/api/command",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({action,value})
  });
  const d=await res.json();
  document.getElementById("message").textContent=d.message||"";
  await poll();
}

async function selectJet(v){
  selectedJet=v;
  await command("select_jet",v);
  scene.remove(playerMesh);
  playerMesh=makeJet(v,true);
  scene.add(playerMesh);
}

async function selectTheater(v){
  selectedTheater=v;
  await command("select_theater",v);
  buildTerrain();
}

function updateButtons(data){
  ["f35","su57","caucasus","persian_gulf","black_sea_georgia"].forEach(id=>{
    const el=document.getElementById(id); if(el)el.classList.remove("active");
  });
  document.getElementById(data.jet_info.short==="F-35"?"f35":"su57").classList.add("active");
  document.getElementById(data.theater).classList.add("active");
}

async function poll(){
  const res=await fetch("/api/state");
  const d=await res.json();
  document.getElementById("jet").textContent=d.jet_info.short;
  document.getElementById("role").textContent=d.jet_info.role;
  document.getElementById("health").textContent=d.health+"%";
  document.getElementById("ammo").textContent=d.ammo;
  document.getElementById("score").textContent=d.score;
  document.getElementById("round").textContent=d.round;
  document.getElementById("objective").textContent=d.objective;
  document.getElementById("progress").textContent=d.progress;
  document.getElementById("message").textContent=d.message;
  document.getElementById("boyMood").textContent=d.characters.boy.mood;
  updateButtons(d);
  syncObjects(d);

  if(d.mission_complete){
    document.getElementById("victoryText").textContent=
      `${d.theater_info.name} // ${d.jet_info.short} // SCORE ${d.score}`;
    document.getElementById("victory").classList.add("show");
  }
}

function closeVictory(){document.getElementById("victory").classList.remove("show");}

addEventListener("resize",()=>{
  if(!camera||!renderer)return;
  camera.aspect=innerWidth/innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth,innerHeight);
});

init3D();
poll();
setInterval(poll,300);

addEventListener("keydown",e=>{
  if(e.key==="ArrowLeft")command("maneuver","left");
  if(e.key==="ArrowRight")command("maneuver","right");
  if(e.key==="ArrowUp")command("maneuver","up");
  if(e.key==="ArrowDown")command("maneuver","down");
  if(e.code==="Space"){e.preventDefault();command("fire");}
});
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
