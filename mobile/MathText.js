import React from 'react';
import {Text} from 'react-native';
export default function MathText({text,style}){return <Text selectable style={[{fontSize:14,lineHeight:25,color:'#172F3C'},style]}>{text}</Text>;}
