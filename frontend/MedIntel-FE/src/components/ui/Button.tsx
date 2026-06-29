import { HTMLMotionProps, motion } from "framer-motion";
import { cn } from "../../lib/utils";

type ButtonProps = HTMLMotionProps<"button"> & {
  variant?: "primary" | "outline" | "ghost";
};

export function Button({ className, variant = "primary", ...props }: ButtonProps) {
  return (
    <motion.button
      whileHover={{ y: props.disabled ? 0 : -1 }}
      whileTap={{ scale: props.disabled ? 1 : 0.98 }}
      className={cn(
        "inline-flex h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-emerald-600/25 disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-emerald-700 text-white shadow-card hover:bg-emerald-800 dark:bg-emerald-500 dark:text-emerald-950 dark:hover:bg-emerald-400",
        variant === "outline" && "border border-emerald-200 bg-white text-emerald-800 hover:bg-emerald-50 dark:border-emerald-900/70 dark:bg-slate-950 dark:text-emerald-300 dark:hover:bg-emerald-950/40",
        variant === "ghost" && "text-slate-600 hover:bg-emerald-50 hover:text-emerald-800 dark:text-slate-300 dark:hover:bg-emerald-950/40 dark:hover:text-emerald-300",
        className,
      )}
      {...props}
    />
  );
}
