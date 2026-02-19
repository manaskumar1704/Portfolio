# Agents & Tech Stack Lock

## 🔒 Locked Tech Stack

**Do NOT introduce new libraries without explicit user approval.**

- **Framework**: Next.js (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS (v4)
- **UI Components**: Shadcn UI (Radix Primitives)
- **Icons**: Lucide React
- **Data Fetching**: TanStack Query
- **Animations**:
  - Framer Motion (Page transitions, UI interactions)
  - Anime.js (Complex sequences)
  - Three.js (3D elements)
- **Package Manager**: Bun

## 🛠️ Coding Standards

- **Components**: Functional components with TypeScript interfaces for props.
- **Styling**: Use utility classes (Tailwind). Avoid inline styles or CSS modules.
- **State**: Use React Hooks (`useState`, `useReducer`) or minimal global state if needed.
- **Clean Code**: Remove unused imports, variables, and console logs before committing.

## 🤖 Agent Instructions

1. **Check this file first**: Before suggesting a new library, check if one in this list can achieve the goal.
2. **Refactor first**: Prefer refactoring existing code over adding new files if possible.
3. **Strict adherence**: If a request conflicts with this stack, warn the user.
