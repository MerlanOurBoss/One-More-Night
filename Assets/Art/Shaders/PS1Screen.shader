// A screen that glows on its own: the picture is not lit by the room. Same vertex snap and fog as PS1 Lit.
Shader "OneMoreNight/PS1 Screen"
{
    Properties
    {
        [MainTexture] _BaseMap ("Picture", 2D) = "black" {}
        _Brightness ("Brightness", Range(0, 2)) = 1
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }

        Pass
        {
            Name "Forward"
            Tags { "LightMode" = "UniversalForward" }

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex Vert
            #pragma fragment Frag

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            TEXTURE2D(_BaseMap);
            SAMPLER(sampler_BaseMap);

            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;
                half _Brightness;
            CBUFFER_END

            float2 _PS1SnapGrid;
            float2 _PS1Fog;
            half3 _PS1FogColor;

            struct Attributes
            {
                float4 positionOS : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                half fog : TEXCOORD1;
            };

            Varyings Vert(Attributes input)
            {
                Varyings output;
                float3 positionWS = TransformObjectToWorld(input.positionOS.xyz);
                float4 clipPos = TransformWorldToHClip(positionWS);
                if (clipPos.w > 0.0)
                    clipPos.xy = floor(clipPos.xy / clipPos.w * _PS1SnapGrid + 0.5) / _PS1SnapGrid * clipPos.w;
                output.positionCS = clipPos;
                output.uv = TRANSFORM_TEX(input.uv, _BaseMap);
                output.fog = saturate((_PS1Fog.y - distance(positionWS, _WorldSpaceCameraPos)) / (_PS1Fog.y - _PS1Fog.x));
                return output;
            }

            half4 Frag(Varyings input) : SV_Target
            {
                half3 color = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, input.uv).rgb * _Brightness;
                return half4(lerp(_PS1FogColor, color, input.fog), 1.0);
            }
            ENDHLSL
        }
    }
}
