import { HTMLMotionProps, motion } from "framer-motion";
import { cn } from "../lib/utils";

export function Card({ className, ...props }: HTMLMotionProps<"div">) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={cn("rounded-xl border border-border bg-white shadow-card transition-colors dark:bg-slate-950", className)}
      {...props}
    />
  );
}
