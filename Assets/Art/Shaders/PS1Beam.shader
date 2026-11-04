// Light in the air: an additive sibling of PS1 Lit, with the same vertex snap and fog.
// Unlike the world, it is shaded per pixel: per-vertex strength shows the mesh grid as squares.
// Vertex alpha is the strength, UV is (across, along the ray). Vertex red marks shaft sheets:
// they fade close to the camera and when seen edge-on. Patches where the light lands leave it at 0.
Shader "OneMoreNight/PS1 Beam"
{
    Properties
    {
        _Color ("Color", Color) = (0.6, 0.65, 0.7, 1)
        _Intensity ("Intensity", Range(0, 1)) = 1
        _NearFade ("Fade Near Camera (start, end)", Vector) = (0.3, 1.2, 0, 0)
        _EdgeFade ("Fade Edge-On (start, end)", Vector) = (0.1, 0.55, 0, 0)
        _Feather ("Soft Edge Width", Range(0.01, 0.5)) = 0.25
    }

    SubShader
    {
        Tags { "RenderType" = "Transparent" "RenderPipeline" = "UniversalPipeline" "Queue" = "Transparent" }

        Pass
        {
            Name "Forward"
            Tags { "LightMode" = "UniversalForward" }
            Blend One One
            ZWrite Off
            Cull Off

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex Vert
            #pragma fragment Frag

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            CBUFFER_START(UnityPerMaterial)
                half4 _Color;
                half _Intensity;
                float4 _NearFade;
                float4 _EdgeFade;
                half _Feather;
            CBUFFER_END

            float2 _PS1SnapGrid;
            float2 _PS1Fog;

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float2 uv : TEXCOORD0;
                half4 color : COLOR;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 positionWS : TEXCOORD1;
                float3 normalWS : TEXCOORD2;
                half4 color : COLOR;
            };

            Varyings Vert(Attributes input)
            {
                Varyings output;
                output.positionWS = TransformObjectToWorld(input.positionOS.xyz);
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                float4 clipPos = TransformWorldToHClip(output.positionWS);
                if (clipPos.w > 0.0)
                    clipPos.xy = floor(clipPos.xy / clipPos.w * _PS1SnapGrid + 0.5) / _PS1SnapGrid * clipPos.w;
                output.positionCS = clipPos;
                output.uv = input.uv;
                output.color = input.color;
                return output;
            }

            half SoftEdges(float x)
            {
                return smoothstep(0.0, _Feather, x) * smoothstep(0.0, _Feather, 1.0 - x);
            }

            half4 Frag(Varyings input) : SV_Target
            {
                float3 toCamera = _WorldSpaceCameraPos - input.positionWS;
                float dist = length(toCamera);
                half fog = saturate((_PS1Fog.y - dist) / (_PS1Fog.y - _PS1Fog.x));
                half strength = input.color.a * fog * SoftEdges(input.uv.x);

                if (input.color.r > 0.5)
                {
                    // Eases in from the window, dies out before it lands.
                    float along = input.uv.y;
                    strength *= smoothstep(0.0, 0.12, along) * (1.0 - along) * (1.0 - along);
                    strength *= saturate((dist - _NearFade.x) / (_NearFade.y - _NearFade.x));
                    strength *= smoothstep(_EdgeFade.x, _EdgeFade.y, abs(dot(normalize(input.normalWS), toCamera / dist)));
                }
                else
                {
                    strength *= SoftEdges(input.uv.y);
                }
                return half4(_Color.rgb * _Intensity * strength, 1.0);
            }
            ENDHLSL
        }
    }
}
