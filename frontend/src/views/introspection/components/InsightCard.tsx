import {
  Box,
  Badge,
  Text,
  VStack,
  HStack,
  Collapse,
  useDisclosure,
  List,
  ListItem,
} from "@chakra-ui/react";
import type { InsightCard as InsightCardType } from "@/types/api";

const SEVERITY_COLORS: Record<InsightCardType["severity"], string> = {
  high: "red",
  medium: "orange",
  low: "purple",
};

const TYPE_DESCRIPTIONS: Record<InsightCardType["type"], string> = {
  skill_forgetting: "Skill Forgetting",
  tool_retry: "Tool Retry Loop",
  context_drift: "Context Drift",
  inefficiency: "Inefficiency",
};

interface InsightCardProps {
  card: InsightCardType;
}

export function InsightCardComponent({ card }: InsightCardProps) {
  const { isOpen, onToggle } = useDisclosure();
  const severityColor = SEVERITY_COLORS[card.severity];

  return (
    <Box
      bg="surface.card"
      borderRadius="soft-lg"
      boxShadow="soft"
      border="1px solid"
      borderColor="soft.border"
      overflow="hidden"
      transition="all 0.2s"
      _hover={{ boxShadow: "md" }}
    >
      {/* Header — always visible, clickable */}
      <Box
        px={5}
        py={4}
        cursor="pointer"
        onClick={onToggle}
        _hover={{ bg: "soft.hover" }}
      >
        <HStack spacing={3} mb={2}>
          <Badge
            colorScheme={severityColor}
            fontSize="xs"
            textTransform="uppercase"
          >
            {card.severity}
          </Badge>
          <Badge variant="outline" colorScheme="gray" fontSize="xs">
            {TYPE_DESCRIPTIONS[card.type]}
          </Badge>
          {card.cross_session && (
            <Badge variant="subtle" colorScheme="blue" fontSize="xs">
              Seen in {card.cross_session.count} of{" "}
              {card.cross_session.total} sessions
            </Badge>
          )}
          <Box flex={1} />
          <Text color="gray.400" fontSize="xs">
            {isOpen ? "\u25BC" : "\u25B6"}
          </Text>
        </HStack>

        <Text fontWeight="600" fontSize="sm" color="gray.800">
          {card.title}
        </Text>
        <Text fontSize="sm" color="gray.600" mt={1}>
          {card.description}
        </Text>

        {/* Occurrences */}
        {card.occurrences.length > 0 && (
          <HStack spacing={2} mt={2} flexWrap="wrap">
            {card.occurrences.map((occ, i) => (
              <Badge
                key={i}
                variant="subtle"
                colorScheme="gray"
                fontSize="xs"
                fontFamily="mono"
              >
                {occ.label} (seq {occ.event_seq})
              </Badge>
            ))}
          </HStack>
        )}
      </Box>

      {/* Expandable detail */}
      <Collapse in={isOpen}>
        <Box
          px={5}
          py={4}
          borderTop="1px solid"
          borderColor="soft.border"
          bg="gray.50"
        >
          <VStack align="stretch" spacing={3}>
            <Box>
              <Text
                fontSize="xs"
                fontWeight="600"
                color="gray.500"
                textTransform="uppercase"
                letterSpacing="wider"
                mb={1}
              >
                Root Cause
              </Text>
              <Text fontSize="sm" color="gray.700">
                {card.root_cause}
              </Text>
            </Box>

            {card.best_practices.length > 0 && (
              <Box>
                <Text
                  fontSize="xs"
                  fontWeight="600"
                  color="gray.500"
                  textTransform="uppercase"
                  letterSpacing="wider"
                  mb={1}
                >
                  Best Practices
                </Text>
                <List spacing={1}>
                  {card.best_practices.map((tip, i) => (
                    <ListItem key={i} fontSize="sm" color="gray.700">
                      <Text as="span" color="brand.500" mr={2}>
                        &bull;
                      </Text>
                      {tip}
                    </ListItem>
                  ))}
                </List>
              </Box>
            )}
          </VStack>
        </Box>
      </Collapse>
    </Box>
  );
}
