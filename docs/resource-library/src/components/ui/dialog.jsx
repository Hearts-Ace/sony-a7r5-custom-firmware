import * as DialogPrimitive from '@radix-ui/react-dialog';
import {X}from'lucide-react';
export const Dialog=DialogPrimitive.Root;export const DialogTrigger=DialogPrimitive.Trigger;export const DialogTitle=DialogPrimitive.Title;export const DialogDescription=DialogPrimitive.Description;
export function DialogContent({children,className,closeLabel="关闭详情",...props}){return <DialogPrimitive.Portal><DialogPrimitive.Overlay className="dialog-overlay"/><DialogPrimitive.Content className={className?`dialog-content ${className}`:'dialog-content'} {...props}>{children}<DialogPrimitive.Close className="dialog-close" aria-label={closeLabel}><X size={18}/></DialogPrimitive.Close></DialogPrimitive.Content></DialogPrimitive.Portal>}
