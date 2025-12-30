# Minecraftfest — Default Player Contract
**Version:** 1.0  
**Applies to:** All non-admin players  
**Scope:** Lobby, Whimbleton, and all future servers  
**Enforcement Layers:** Velocity → Paper → Plugins

---

## 1. Identity & Admission (Network-Level)

- Players may join the Minecraftfest network **only if**:
  - They are present in the Velocity whitelist group `approved`
  - Access is enforced at the **Velocity proxy**, not backend servers
- Backend server whitelists are **disabled**
- Admission is UUID-based; username changes do not affect access
- No implicit bypasses exist for default players

**Non-goals**
- No “temporary open” states
- No per-server admission differences

---

## 2. Communication & Chat

### Allowed
- Public chat
- Private messages:
  - `/msg`
  - `/w`
  - `/tell`
  - `/r`
- Immediate chat on join (no movement or time gating)

### Disallowed
- Muting other players
- Message spying or social spy features
- Bypassing chat filters or moderation tools

### Guarantees
- Chat behavior is identical across all servers
- No plugin may require movement, delay, or interaction before chatting

---

## 3. Information Visibility

### Players MAY see:
- `/help` (sanitized)
- `/list` (no staff or hidden-role leakage)

### Players MUST NOT see:
- `/plugins`, `/pl`
- `/version`, `/ver`, `/about`
- Server, proxy, or platform details
- Admin-only commands via tab completion

This is considered an **information disclosure boundary**.

---

## 4. World Interaction & Gameplay

### Allowed
- Free movement
- Interaction with blocks as permitted by GriefPrevention
- Building only within owned or permitted claims
- Normal survival/adventure gameplay mechanics

### Disallowed
- Editing protected spawn areas
- Bypassing GriefPrevention claims
- Altering world rules, difficulty, time, or weather

World protection behavior must be **consistent** across servers unless explicitly documented.

---

## 5. Power & Authority (Explicitly Forbidden)

Default players must never have access to:

- Operator status or OP-equivalent permissions
- Permissions management (LuckPerms, etc.)
- Server control commands:
  - `/stop`, `/restart`, `/reload`
- Administrative utilities:
  - `/fly`, `/god`, `/vanish`, `/invsee`
- Gamemode changes
- WorldEdit or similar tools

If a default player can do **any** of the above, the contract is broken.

---

## 6. Cross-Server Consistency

The following must behave **identically** on:
- Lobby
- Whimbleton
- Any future Minecraftfest server

Including but not limited to:
- Chat and whisper behavior
- Permission visibility
- Command availability
- Spawn and join experience

Any intentional deviation must be:
1. Explicit
2. Documented
3. Testable

---

## 7. Enforcement & Testing

This contract is enforced through:
- Velocity whitelist (`approved` group)
- LuckPerms default group permissions
- Essentials (QoL only, not authority)
- GriefPrevention (claims, not admission)
- Explicit command aliasing (`/w` → `essentials:msg`)

### Acceptance Test (Non-Admin Player)
A default player must:
- Be blocked entirely if removed from Velocity whitelist
- Be able to chat and whisper immediately on join
- Be unable to view plugins, versions, or admin tools
- Experience identical behavior across all servers

---

## 8. Change Policy

- Any new plugin must be evaluated against this contract
- Any permission change must be validated against this contract
- This document is the **source of truth** for default player behavior

If behavior differs from this contract, **the behavior is wrong**, not the contract.

---

*End of Default Player Contract*