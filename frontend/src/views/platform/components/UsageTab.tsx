import { Center, Text } from "@chakra-ui/react";
import { DARK } from "@/shared/utils/gatewayColors";

export default function UsageTab(_props: { days: number; endpoint: string | null }) {
  return <Center py={20}><Text color={DARK.label}>Usage tab — coming soon</Text></Center>;
}
