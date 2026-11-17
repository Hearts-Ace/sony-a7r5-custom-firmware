import * as DialogPrimitive from '@radix-ui/react-dialog';
import {X}from'lucide-react';
export const Dialog=DialogPrimitive.Root;export const DialogTrigger=DialogPrimitive.Trigger;export const DialogTitle=DialogPrimitive.Title;export const DialogDescription=DialogPrimitive.Description;
export function DialogContent({children}){return <DialogPrimitive.Portal><DialogPrimitive.Overlay className="dialog-overlay"/><DialogPrimitive.Content className="dialog-content">{children}<DialogPrimitive.Close className="dialog-close" aria-label="关闭详情"><X size={18}/></DialogPrimitive.Close></DialogPrimitive.Content></DialogPrimitive.Portal>}
