import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-[var(--radius-sm)] border border-transparent bg-clip-padding text-[15px] font-medium whitespace-nowrap outline-none select-none touch-manipulation transition-[color,background-color,border-color,opacity,box-shadow] duration-[var(--duration)] ease-[var(--ease)] focus-visible:[box-shadow:var(--focus)] active:not-aria-[haspopup]:scale-[0.98] disabled:pointer-events-none disabled:opacity-40 aria-invalid:border-[var(--danger)] [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--accent)] text-white hover:brightness-105 [box-shadow:var(--inner-highlight)]",
        outline:
          "border-[var(--border)] bg-[var(--surface)] text-[var(--text)] backdrop-blur-[var(--glass-blur-strong)] hover:border-[var(--border-alt)] hover:bg-[var(--surface-strong)] aria-expanded:border-[var(--border-alt)] aria-expanded:bg-[var(--surface-strong)] [box-shadow:var(--inner-highlight)]",
        secondary:
          "border-[var(--border)] bg-[var(--surface)] text-[var(--text)] backdrop-blur-[var(--glass-blur-strong)] hover:border-[var(--border-alt)] hover:bg-[var(--surface-strong)] aria-expanded:border-[var(--border-alt)] [box-shadow:var(--inner-highlight)]",
        ghost:
          "text-[var(--text-muted)] hover:bg-[var(--accent-soft)] hover:text-[var(--text)] aria-expanded:bg-[var(--accent-soft)] aria-expanded:text-[var(--text)]",
        destructive:
          "text-[var(--danger)] hover:bg-[color-mix(in_srgb,var(--danger)_12%,transparent)]",
        link: "text-[var(--accent)] underline-offset-4 hover:underline",
      },
      size: {
        default:
          "h-8 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        xs: "h-6 gap-1 rounded-[var(--radius-sm)] px-2 text-[13px] in-data-[slot=button-group]:rounded-[var(--radius-sm)] has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 rounded-[var(--radius-sm)] px-2.5 text-[13px] in-data-[slot=button-group]:rounded-[var(--radius-sm)] has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-9 gap-1.5 px-3 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        icon: "size-8",
        "icon-xs":
          "size-6 rounded-[var(--radius-sm)] in-data-[slot=button-group]:rounded-[var(--radius-sm)] [&_svg:not([class*='size-'])]:size-3",
        "icon-sm":
          "size-7 rounded-[var(--radius-sm)] in-data-[slot=button-group]:rounded-[var(--radius-sm)]",
        "icon-lg": "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
