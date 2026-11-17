import * as React from 'react';
import {Slot} from '@radix-ui/react-slot';
import {cva} from 'class-variance-authority';
import {cn} from '@/lib/utils';
const buttonVariants=cva('ui-button',{variants:{variant:{default:'ui-primary',secondary:'ui-secondary',ghost:'ui-ghost',outline:'ui-outline'},size:{default:'',sm:'ui-small',icon:'ui-icon'}},defaultVariants:{variant:'default',size:'default'}});
const Button=React.forwardRef(({className,variant,size,asChild=false,...props},ref)=>{const Comp=asChild?Slot:'button';return <Comp ref={ref} className={cn(buttonVariants({variant,size,className}))} {...props}/>});Button.displayName='Button';
export {Button,buttonVariants};
