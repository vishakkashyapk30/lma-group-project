"use client";
// DropdownMenu (Radix): arrow keys, type-ahead and Escape come with it.
import * as MenuPrimitive from "@radix-ui/react-dropdown-menu";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";
import { cn } from "@/lib/utils";

export const DropdownMenu = MenuPrimitive.Root;
export const DropdownMenuTrigger = MenuPrimitive.Trigger;
export const DropdownMenuGroup = MenuPrimitive.Group;

export const DropdownMenuContent = forwardRef<ElementRef<typeof MenuPrimitive.Content>, ComponentPropsWithoutRef<typeof MenuPrimitive.Content>>(
  function DropdownMenuContent({ className, sideOffset = 6, align = "end", ...props }, ref) {
    return (
      <MenuPrimitive.Portal>
        <MenuPrimitive.Content
          ref={ref}
          sideOffset={sideOffset}
          align={align}
          className={cn(
            "z-modal min-w-[13rem] overflow-hidden rounded-lg border border-line bg-cream p-1 text-sm text-ink shadow-lg data-[state=open]:animate-scale-in",
            className,
          )}
          {...props}
        />
      </MenuPrimitive.Portal>
    );
  },
);

export const DropdownMenuItem = forwardRef<ElementRef<typeof MenuPrimitive.Item>, ComponentPropsWithoutRef<typeof MenuPrimitive.Item>>(
  function DropdownMenuItem({ className, ...props }, ref) {
    return (
      <MenuPrimitive.Item
        ref={ref}
        className={cn(
          "flex cursor-default select-none items-center gap-2 rounded-md px-2.5 py-1.5 outline-none data-[highlighted]:bg-parchment-deep data-[disabled]:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:text-ink-muted",
          className,
        )}
        {...props}
      />
    );
  },
);

export const DropdownMenuLabel = forwardRef<ElementRef<typeof MenuPrimitive.Label>, ComponentPropsWithoutRef<typeof MenuPrimitive.Label>>(
  function DropdownMenuLabel({ className, ...props }, ref) {
    return <MenuPrimitive.Label ref={ref} className={cn("px-2.5 py-1.5 text-xs font-semibold text-ink-muted", className)} {...props} />;
  },
);

export const DropdownMenuSeparator = forwardRef<ElementRef<typeof MenuPrimitive.Separator>, ComponentPropsWithoutRef<typeof MenuPrimitive.Separator>>(
  function DropdownMenuSeparator({ className, ...props }, ref) {
    return <MenuPrimitive.Separator ref={ref} className={cn("my-1 h-px bg-line", className)} {...props} />;
  },
);
