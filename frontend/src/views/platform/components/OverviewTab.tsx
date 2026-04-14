import { Center, Text } from "@chakra-ui/react";
import { DARK } from "@/shared/utils/gatewayColors";

export default function OverviewTab(_props: { days: number; endpoint: string | null }) {
  return <Center py={20}><Text color={DARK.label}>Overview tab — coming soon</Text></Center>;
}
