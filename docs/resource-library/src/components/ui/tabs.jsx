import * as TabsPrimitive from '@radix-ui/react-tabs';
import {cn} from '@/lib/utils';
export const Tabs=TabsPrimitive.Root;
export function TabsList({className,...props}){return <TabsPrimitive.List className={cn('ui-tabs-list',className)} {...props}/>}
export function TabsTrigger({className,onPointerDownCapture,onKeyDownCapture,onBlur,...props}){return <TabsPrimitive.Trigger className={cn('ui-tabs-trigger',className)} {...props} onPointerDownCapture={e=>{e.currentTarget.dataset.pointerFocus='true';onPointerDownCapture?.(e);}} onKeyDownCapture={e=>{delete e.currentTarget.dataset.pointerFocus;onKeyDownCapture?.(e);}} onBlur={e=>{delete e.currentTarget.dataset.pointerFocus;onBlur?.(e);}}/>}
export function TabsContent({className,...props}){return <TabsPrimitive.Content className={cn('ui-tabs-content',className)} {...props}/>}
