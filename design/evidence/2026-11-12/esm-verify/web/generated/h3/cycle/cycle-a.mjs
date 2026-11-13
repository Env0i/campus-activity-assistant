/* 顶层互相引用的循环：a 在顶层读 b 的常量，b 又 import a */
import { b } from './cycle-b.mjs';

export const a = 'a' + b;
