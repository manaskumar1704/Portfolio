import { render, screen } from '@testing-library/react'
import ThemeToggle from '@/components/ThemeToggle'
import { ThemeProvider } from '@/components/ThemeProvider'
import { describe, it, expect, vi } from 'vitest'

// Mock next-themes
vi.mock('next-themes', async () => {
    const actual = await vi.importActual('next-themes')
    return {
        ...actual,
        useTheme: () => ({
            theme: 'dark',
            setTheme: vi.fn(),
        }),
    }
})

describe('ThemeToggle', () => {
    it('renders theme toggle button', () => {
        render(
            <ThemeProvider>
                <ThemeToggle />
            </ThemeProvider>
        )

        // Check if button exists (using aria-label or role)
        const button = screen.getByRole('button', { name: /toggle theme/i })
        expect(button).toBeDefined()
    })
})
