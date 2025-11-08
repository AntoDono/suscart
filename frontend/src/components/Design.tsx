// @ts-nocheck
import { Sparkles } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useRef } from 'react'
export const Design = () => {
    const bluePoints = useRef<any>( null )
    const whitePoints = useRef<any>( null );

    useFrame( ( state: any ) => {
        if ( !bluePoints.current || !whitePoints.current ) return;

        bluePoints.current.rotation.y += 0.00002;
        whitePoints.current.rotation.y += 0.000092;

    } )
    return (
        <>
            <Sparkles
                ref={ bluePoints }
                size={ 2.5 }
                position={ [ 0, 0, 0 ] }
                scale={ 8 }
                color="#5787F5"
                // transparent
            />
            <Sparkles
                ref={ whitePoints }
                size={ 2.3 }
                scale={ 8 }
                position={ [ 0, 0, 0 ] }
                color="white"
                // transparent//
            />
        </>
    )
}