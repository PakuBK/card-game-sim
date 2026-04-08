# Bazaar Combat Simulation Engine

## Project Goal and Software Context

## 1. Overview

The goal of this project is to build a **combat simulation engine inspired by the game _The Bazaar_**. The engine will allow users to **define custom items, boards, and combat configurations**, and then simulate fights between two players to analyze outcomes.

Unlike a typical game implementation, this system is not meant to reproduce the full game environment. Instead, it is designed as a **theory-crafting and experimentation tool** that focuses exclusively on the **combat system**.

The simulator will allow users to:
- Create **custom item definitions**
- Configure **player boards**
- Simulate **combat interactions**
- Run **multiple simulations**
- Analyze **combat statistics and outcomes**

The system is intended to support **rapid experimentation with item designs and combat strategies**.

## 1.1 Relevant Documentation

- [[engine_data_model| Engine Data Model]] > Technical details for the implementation

---

# 2. Core Design Philosophy

The most important design constraint of the system is:

> **Items must be fully user-defined and transmitted as data.**

This means that item behavior cannot be hardcoded in the backend.

Instead, the backend will provide a **generic combat engine** that interprets item definitions sent from the frontend.

This leads to a separation between:

**Engine Logic**
- Implemented in Python
- Responsible for combat simulation
- Executes triggers, effects, timers, and status interactions
    
**Game Content**
- Defined as **data**
- Created in the frontend
- Sent to the backend for execution
    
This architecture enables the simulator to function as a **sandbox environment for designing and testing new items**.

---

# 3. System Architecture

The system consists of two primary components.

## 3.1 Frontend (React)

The frontend provides a **graphical interface** where users can:

- Design custom items
- Configure player boards
- Define player statistics
- Run simulations
- View combat results and statistics 

The frontend will act as a **visual editor for the combat configuration**.
It produces structured data describing:
- Item definitions
- Player setups
- Board layouts
- Simulation parameters
    
This data is sent to the backend as **JSON**.

---
## 3.2 Backend (Python)

The backend hosts the **combat simulation engine**.

Responsibilities include:
- Parsing item definitions
- Building runtime objects
- Running combat simulations
- Processing events and interactions
- Returning combat statistics
    
The backend does **not store permanent item definitions**. Instead, items are provided dynamically by the frontend.

The backend acts as a **deterministic execution engine**.

---

# 4. Simulation Scope

The simulator focuses **exclusively on combat mechanics**.

The following gameplay elements are included:

## Players
Each player has:
- Maximum Health
- Current Health
- Shield
- Regeneration
- Status effects (Burn, Poison)
    
## Boards
Each player has a **board containing items**.

Board characteristics:
- Fixed width (default: 10 units)
- Items occupy **1–3 units**
- Item placement determines adjacency relationships

## Time Model  
  
Combat simulation operates using a **discrete-event time model** rather than a fixed timestep simulation.  
  
Instead of advancing time in small increments (e.g., every 0.01 seconds), the engine **jumps directly from one event to the next** on the combat timeline.  
  
This approach is known as a **discrete-event simulation** and is commonly used in high-performance simulation systems.  
  
Advantages of this model include:  
  
- **High precision** (no floating-point drift from repeated time increments)  
- **High performance** (the engine skips periods where nothing happens)  
- **Deterministic execution**  
- Efficient support for **thousands of simulations**  
  
Because the simulator does not need to render real-time visuals, it can take full advantage of this event-driven approach.  
  
---
### Event Queue  
  
All scheduled actions in the simulation are stored in a **priority event queue** sorted by time.  
  
Each event contains:  
```
Event {  
	time  
	type  
	source  
	target  
	payload  
}
```

Example queue:  
```
1.0 -> Item B Use  
1.5 -> Item A Use  
2.0 -> Burn Tick  
3.0 -> Poison Tick
```

The engine repeatedly performs the following loop:  

```
while event_queue not empty:

event = pop_next_event()  
  
current_time = event.time  
  
process_event(event)
```
  
This means the simulation **skips directly to the next relevant moment in time**.  
  
---  
  
### Timer Representation  
  
Item cooldowns are represented using **absolute trigger times** rather than remaining time.  
  
Example:  
```
current_time = 8

Item A  
cooldown = 4  
next_use = 12
```

  
The remaining cooldown is computed when needed:  
`remaining = next_use - current_time`

This avoids cumulative floating-point errors that occur in timestep-based systems.  

>[!example] Basic Timer Example
> Consider two items: 
> `Item A cooldown = 1.5`
> `Item B cooldown = 1.0`
> At simulation start:  
> `current_time = 0`
> Scheduled events:  
> `1.0 -> Item B Use`  
> `1.5 -> Item A Use`
> Execution:  
> `t = 1.0 Item B triggers`  
> `t = 1.5 Item A triggers`
> After Item B triggers, it schedules its next use:  
> `next_use = current_time + cooldown`  
> `next_use = 1.0 + 1.0 = 2.0`
> Updated queue:  
> `1.5 -> Item A Use`
> `2.0 -> Item B Use` 

---
### Status Effect Ticks  
  
Status effects such as **Burn** and **Poison** schedule periodic events.  
Example: Burn ticks every **0.5 seconds**.  
When Burn is applied:  
`schedule event:`  
`time = current_time + 0.5`  
`type = BURN_TICK`

When a burn tick occurs:  
1. Damage is applied.  
2. Burn value is reduced.  
3. The next tick is scheduled.  

Example timeline:  
`0.5 -> Burn Tick`  
`1.0 -> Burn Tick`  
`1.5 -> Burn Tick`

---
### Timer Progression Modifiers  

Some item status effects modify how quickly cooldown timers progress.  
  
| Effect | Behavior                                  |
| ------ | ----------------------------------------- |
| Slow   | Cooldown progresses at **50% speed**      |
| Haste  | Cooldown progresses at **200% speed**     |
| Freeze | Cooldown progression **stops completely** |

Because the engine uses absolute trigger times, these modifiers require **timer recalculation** when they start or end.  
  
Whenever a timer modifier changes:  
1. The remaining cooldown is calculated.  
2. The existing scheduled event is cancelled.  
3. The timer is recalculated using the new speed.  
4. A new event is scheduled.  
  
---
### Examples  

#### Slow Example

Initial state:  
```
Item cooldown = 4  
current_time = 8  
next_use = 12  
remaining = 4
```

A **Slow effect lasting 2 seconds** is applied.  
Slow progression rate:  `speed = 0.5`

Cooldown progression during Slow:  
`progress = duration × speed`  
`progress = 2 × 0.5 = 1`

Remaining cooldown after Slow ends:  
`remaining = 4 - 1 = 3`

Slow ends at:  `time = 10`
  
Final trigger time:  
`next_use = 10 + 3`  
`next_use = 13`

Result:  
`original trigger: 12`  
`actual trigger: 13`

---  
#### Haste Example  
  
Initial state:  
```
Item cooldown = 4  
current_time = 8  
next_use = 12  
remaining = 4
```

A **Haste effect lasting 2 seconds** is applied.  
Haste progression rate:  `speed = 2`

  
Cooldown progression during Haste:  
`progress = duration × speed`  
`progress = 2 × 2 = 4`

Since the full cooldown completes during the Haste window:  
`remaining = 4 - 4 = 0`
The item triggers at:  `time = 10`

Result:  
`original trigger: 12`  
`actual trigger: 10`
  
---  
#### Freeze Example  

Initial state:  
```
Item cooldown = 4  
current_time = 8  
next_use = 12  
remaining = 4
```

Freeze is applied for **2 seconds**. 

During Freeze:  `progression speed = 0`
Cooldown does not progress.  

When Freeze ends:  
`time = 10`  
`remaining = 4`

New trigger time:  
`next_use = 10 + 4`  
`next_use = 14`

Result:  
`original trigger: 12`  
`actual trigger: 14`
  
---  
#### Multiple Timer Modifiers  
  
Because modifier events themselves are part of the event system, timers can respond dynamically to new changes.  
  
Example timeline:  
```
t=8 Slow applied  
t=9 Charge applied  
t=10 Slow removed  
t=12.5 Item triggers
```

Each modifier event causes the timer to be recalculated based on the **current remaining cooldown and progression rate**.  

This ensures the system remains **accurate and deterministic** even when many interactions occur simultaneously.  
  
---  
### Summary  
  
The combat engine uses a **discrete-event simulation model** with an event priority queue.  
  
Key properties of the time model:  
  
- Time advances **directly to the next scheduled event**  
- Item timers store **absolute trigger times**  
- Status effects schedule **periodic events**  
- Timer modifiers cause **event rescheduling**  
- The system avoids timestep iteration entirely  
  
This model allows the engine to simulate large numbers of fights efficiently while maintain

---
## Items
Items are the **primary source of combat behavior**.

Items may:
- Apply poison or burn to any player
- Heal any player
- Deal Damage to any player
- Generate shield to any player
- Modify other items (enemy or own)
- Trigger effects based on events

Items may also interact with:
- Adjacent items
- Random items
- Specific item types
- Enemy items

#### Item Size
- Item occupy space units on the board. 
- Item size range from a minimum of one to a maximum of three.
- Items can be placed with space between them if enough space is on the board.
- Item position is a vital part of the simulation.
- Item position can't be switched in the fight, there position is set beforehand.



---
## Status Effects

### Burn Status Effect

**Burn** is a damage-over-time status effect applied to players. It deals periodic damage and gradually decreases in intensity over time.

#### Burn Damage Ticks

Burn deals damage **twice per second** (every 0.5 seconds).

At each tick:
1. Burn deals damage equal to its current Burn value.
2. The Burn value is reduced by **3%**, with a minimum reduction of 1 (rounded up).
3. The process repeats until the Burn value reaches **0**.
    

>[!example] **50** Burn Example

| Tick | Burn | Damage | Decrease                                  |
| ---- | ---- | ------ | ----------------------------------------- |
| 0    | 50   | 0      | $50 \times 0.03 = \lceil 1.5 \rceil = 2$  |
| 1    | 48   | 50     | $48 \times 0.03 = \lceil 1.44 \rceil = 2$ |
| 2    | 46   | 48     | $46 \times 0.03 = \lceil 1.38 \rceil = 2$ |

>[!example] **9** Burn Example

| Tick | Burn | Damage | Decrease                                 |
| ---- | ---- | ------ | ---------------------------------------- |
| 0    | 9    | 0      | $9 \times 0.03 = \lceil 0.27 \rceil = 1$ |
| 1    | 8    | 9      | $8 \times 0.03 = \lceil 0.24 \rceil = 1$ |


Burn stacks additively, meaning applying additional Burn increases the current Burn value.

---
#### Interaction with Shield
Burn damage is partially mitigated by **Shield**.

If the player has any Shield when a Burn tick occurs, the portion of Burn damage that interacts with Shield is **halved**.

However, the amount of Burn damage that can benefit from this reduction is **capped by the current Shield value**.

This means that Shield can only reduce Burn damage for the portion of Burn that it can actually absorb.

The remaining Burn damage bypasses this reduction.
#### Calculation
At each Burn tick:
1. Determine the Burn value **B**.
2. Determine the current Shield value **S**.
3. Split the Burn damage into two parts:
- **Shield-interacting Burn:** `min(B, S)`
- **Remaining Burn:** `B - min(B, S)`

The Shield-interacting portion is **halved**, while the remaining portion is applied at full value.

#### Example

Burn = 10  
Shield = 2

```
Shield-interacting Burn = 2
Halved damage = 1

Remaining Burn = 8
Full damage = 8

Total damage = 9
```

After the damage is applied, the Burn value decreases by **1** (3% of 10).

---
#### Healing Interaction

Healing received by the player reduces Burn.
Whenever a player receives healing:

```
Burn reduction = 5% of the heal amount
```

This reduction is applied directly to the current Burn value.

**Lifesteal healing does not reduce Burn.**
**Regeneration does not count as healing recieved.**

---

#### Summary of Burn Behavior
- Deals damage **every 0.5 seconds**
- Damage equals the **current Burn value**
- Burn decreases by **3%** each tick, rounded up with a minimal of 1.
- **Shield halves Burn damage**, but only for the portion covered by Shield
- Remaining Burn damage is applied normally
- **Healing reduces Burn by 5% of the heal amount**
- **Lifesteal healing does not reduce Burn**
- **Regeneration healing does not reduce Burn**

---
### Poison Status Effect

**Poison** is a damage-over-time status effect applied to players. It deals periodic damage but **does not decrease on its own**, making it a persistent source of damage unless removed by other effects.

#### Poison Damage Ticks
Poison deals damage **once per second**.
At each tick:
1. Poison deals damage equal to its current Poison value.
2. The Poison value **does not decrease** after the damage is applied.

Example:
- A player with **Poison = 50** will take:
    - 50 damage after 1 second
    - 50 damage after 2 seconds
    - 50 damage after 3 seconds
    - and so on.
        
Poison stacks additively, meaning applying additional Poison increases the total Poison value on the player.

---

#### Interaction with Shield
Poison **bypasses Shield entirely**.

Damage dealt by Poison is applied **directly to the player's Health**, ignoring any Shield the player currently has.

Example:
Health = 100  
Shield = 500  
Poison = 50
After one second:

```
Poison damage = 50
Shield remains = 500
Health becomes = 50
```

---
#### Healing Interaction

Healing received by the player reduces Poison.

Whenever a player receives healing:

```
Poison reduction = 5% of the heal amount
```

This reduction is applied directly to the current Poison value.

**Lifesteal healing does not reduce Poison.**
**Regeneration healing does not reduce Poison.**

Example:
Poison = 40  
Player receives 200 healing

```
Poison reduction = 200 × 0.05 = 10
New Poison value = 30
```

---
#### Summary of Poison Behavior
- Deals damage **every 1 second**
- Damage equals the **current Poison value**
- Poison **does not decay over time**
- **Bypasses Shield completely**
- **Healing reduces Poison by 5% of the heal amount**
- **Lifesteal healing does not reduce Poison**
- **Regeneration healing does not reduce Poison.**
- Poison stacks **additively**

---
### Item Status Effects
Items can receive temporary status effects:

| Effect | Description                                                        |
| ------ | ------------------------------------------------------------------ |
| Slow   | Timer Cooldown progresses at 50% speed                             |
| Haste  | Timer Cooldown progresses at 200% speed                            |
| Freeze | Timer Cooldown progression stops                                   |
| Charge | Instantly reduces remaining cooldown                               |
| Flight | **Flying** items are affected by Freeze and Slow for half as long. |

---
#### Slow
Slow reduces the **cooldown progression speed** of an item.

Effect: Cooldown speed × 0.5

>[!example] Example
>Item cooldown = 2s
>With Slow:
>Effective cooldown = 4s

---

#### Haste
Haste increases cooldown progression speed.

Effect: Cooldown speed × 2

Example:
Item cooldown = 2s
With Haste:
Effective cooldown = 1s

---
#### Freeze
Freeze **pauses cooldown progression**.

Properties:
-   Cooldown does **not decrease**
-   The item cannot trigger
-   The effect lasts for a defined **freeze duration**

------------------------------------------------------------------------

#### Charge
Charge is an **instant effect**, not a status effect.

Properties:
-   Reduces the **remaining cooldown** by a fixed value.

Example:
Item cooldown = 3s
Remaining cooldown = 1s
Applying: Charge 1
Result: Remaining cooldown = 0

The item **triggers immediately**.

---

# 5. Item Definition Model

Since items are user-generated, they must be expressed as **data structures**.

Each item definition will consist of several components.
## 5.1 Stats (Values)

Stats represent the **numerical attributes of the item**.

Examples:
- Damage
- Cooldown
- Poison
- Burn
- Shield
- Heal
- Ammo
- Multicast

Stats serve as inputs for item effects.

---

## 5.2 Runtime State

During combat, items maintain runtime state such as:
- Remaining cooldown
- Active status effects
- Remaining ammo
- Temporary stat modifications
    
This state evolves dynamically throughout the fight.

---

## 5.3 Triggers
Triggers define **when an item reacts to an event**.
A trigger listens for a specific **combat event** and executes its effects when conditions are satisfied.
Typical trigger events include:
- Item use
- Status effect application
- Damage dealt
- Item hasted/frozen/slowed
- Player actions

Triggers follow a general structure:

```
WHEN <Event>
IF <Conditions>
EXECUTE <Effects>
```

---

## 5.4 Effects

Effects describe **what happens when a trigger activates**.

Common effect types include:
- Apply Damage
- Apply Poison
- Apply Burn
- Heal Player
- Apply Shield
- Modify Item Stats
- Charge Item Cooldown
- Apply Item Status Effect

Effects target entities such as:
- Self
- Enemy player
- Friendly items
- Enemy items
- Adjacent items
- Left/Leftmost/Right/Rightmost item
- Random item(s)

---

## 5.5 Expressions

To support dynamic calculations, values may be expressed using structured expressions.

Example:

```
Burn = 10% of this item's damage
```

This must be encoded as structured data rather than executable code.
Example expression:

```
multiply(
    stat("damage"),
    0.1
)
```

This ensures the system remains **safe and deterministic**.

---

# 6. Event-Driven Combat Engine

The combat simulation operates as an **event-driven system**.
During combat, events are continuously generated, such as:

- Item use
- Damage applied
- Status effects triggered
- Cooldown completion
- Time ticks
    
Items subscribe to these events through their triggers.
When an event occurs:

1. The event is dispatched.
2. All relevant triggers are evaluated.
3. Matching triggers execute their effects.
4. Effects may generate new events.
    
This process continues until the fight ends, or we reach the set simulation time limit.

---

# 7. Simulation Execution

The simulation engine supports two primary modes.

### Single Simulation (Debug Mode)

Used for inspecting combat interactions step-by-step.

Provides:
- Event timeline
- Trigger activations
- Damage logs
- Status changes

### Batch Simulation (Statistical Mode)
Runs many simulations to generate statistics.
Typical outputs:
- Win rate
- Average damage
- Average fight duration
- Damage distribution

This allows users to analyze **strategy effectiveness**.

---

# 8. Performance Considerations

The engine must support **large numbers of simulations**.

To achieve this:
- Item definitions will be **compiled into efficient runtime structures**
- JSON parsing will occur **once per simulation batch**
- The event system will minimize dynamic allocations
- The simulation loop will be optimized for repeated execution
    
The goal is to enable **thousands of fight simulations per request**.

---

# 9. Intended Use Cases

The simulator is designed for several use cases:
### Strategy Analysis

Players can test builds against different opponents.

### Item Design

Users can experiment with hypothetical item designs.

### Balance Exploration

Users can observe how stat changes affect combat outcomes.

### Theorycrafting

Complex interactions can be explored without needing the full game.

---

# 10. Summary

This project aims to build a **flexible combat simulation engine** capable of executing dynamically defined item behaviors.

Key characteristics of the system include:
- **Event-driven combat model**
- **User-defined item logic**
- **Data-driven behavior definitions**
- **React-based configuration interface**
- **Python simulation backend**
- **Statistical combat analysis**
    

The final result will be a **powerful sandbox for designing, testing, and analyzing combat systems inspired by _The Bazaar_**.