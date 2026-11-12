import React, { forwardRef } from 'react';
import { CameraView } from 'expo-camera';
export default forwardRef(function LiveCamera(props,ref){return <CameraView ref={ref} {...props} autofocus="on" mode="picture" zoom={0}/>;});
