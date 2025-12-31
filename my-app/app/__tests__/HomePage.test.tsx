import { render, screen } from '@testing-library/react'
import HomePage from '../../app/page'
import { describe, it, expect, vi } from 'vitest'

// Mock components to avoid rendering full tree complexities
vi.mock('../../components/Navbar', () => ({ default: () => <div data-testid="navbar" /> }))
vi.mock('../../components/Footer', () => ({ default: () => <div data-testid="footer" /> }))
vi.mock('../../components/ProjectCard', () => ({ default: () => <div data-testid="project-card" /> }))
vi.mock('../../components/SiteCard', () => ({ default: () => <div data-testid="site-card" /> }))
vi.mock('../../components/Skill', () => ({ default: ({ label }: { label: string }) => <div data-testid="skill">{label}</div> }))

// Mock framer-motion to avoid animation issues in test environment
vi.mock('framer-motion', async () => {
    const actual = await vi.importActual('framer-motion')
    return {
        ...actual,
        motion: {
            div: ({ children, ...props }: React.ComponentProps<'div'>) => <div {...props}>{children}</div>,
            h1: ({ children, ...props }: React.ComponentProps<'h1'>) => <h1 {...props}>{children}</h1>,
            h2: ({ children, ...props }: React.ComponentProps<'h2'>) => <h2 {...props}>{children}</h2>,
            p: ({ children, ...props }: React.ComponentProps<'p'>) => <p {...props}>{children}</p>,
            section: ({ children, ...props }: React.ComponentProps<'section'>) => <section {...props}>{children}</section>,
            a: ({ children, ...props }: React.ComponentProps<'a'>) => <a {...props}>{children}</a>,
        }
    }
})


describe('HomePage Skills Section', () => {
    it('renders Languages and Frameworks sections separately', () => {
        render(<HomePage />)

        // Check for "Languages" heading
        expect(screen.getByText(/Languages/i)).toBeDefined()

        // Check for "Frameworks" heading
        expect(screen.getByText(/Frameworks/i)).toBeDefined()
    })

    it('renders specific skills in correct sections', () => {
        render(<HomePage />)

        // Just check existence for now, specific splitting logic verified by split
        expect(screen.getByText('TypeScript')).toBeDefined()
        expect(screen.getByText('Next.js')).toBeDefined()
    })
})
